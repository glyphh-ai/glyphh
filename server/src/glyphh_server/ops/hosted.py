"""Hosted runtimes on Fly: one machine and one volume per person, made the first time the person starts theirs, on
any plan. The runtime token goes into the machine's environment (nobody signs in on it); its licence and its keys
come in its welcome. It is reached at its own address, `https://<machine>.<domain>`, through Fly's proxy: a request
starts a stopped machine, and the doorman machine (one per app, made with the first runtime) replays a request that
landed elsewhere. The server stops a runtime that sat idle, tallies its online time against the plan's hours, and
past them sends `pause` (rrotor answers 402) until the month turns; `state` is `stopped` until its hello, `online`
while linked, `offline` after a link dropped."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Rrotor, Run, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.link.protocol import RUNNING, WAITING
from glyphh_server.ops.runtimes import NOT_LINKED, HostedRuntime, hosted_view

log = logging.getLogger("glyphh.runtime")

DOORMAN: str = "doorman"


def machine_env(settings: Settings, runtime_id: uuid.UUID, token: str) -> dict[str, str]:
    """What the hosted rrotor needs: where Glyphh is, who it is, and its token (rrotor docs, section 11)."""
    return {
        "RROTOR_MODE": "hosted",
        "RROTOR_SERVER": settings.base_url,
        "RROTOR_RUNTIME_ID": str(runtime_id),
        "RROTOR_RUNTIME_TOKEN": token,
        "RROTOR_PUBLIC_DOMAIN": settings.fly_public_domain,
    }


async def ensure_doorman(fly: Fly, settings: Settings) -> str:
    """The app's one always-on doorman machine, made the first time any runtime is: what Fly's proxy lands a
    request on when the right machine is stopped, so it can be replayed there."""
    for machine in await fly.list_machines():
        if machine.get("name") == DOORMAN:
            return str(machine["id"])
    env = {"RROTOR_MODE": "doorman", "RROTOR_PUBLIC_DOMAIN": settings.fly_public_domain}
    machine_id = await fly.create_machine(DOORMAN, None, env, always_on=True)
    await fly.start(machine_id)
    log.info("doorman made", extra=fields(machine=machine_id))
    return machine_id


async def _provision(conn: AsyncConnection, fly: Fly, settings: Settings, who: Principal) -> uuid.UUID:
    """The person's machine and volume, and the runtime row they belong to; the token is only ever in the machine."""
    token = make_secret()
    values = {
        "user_id": who.user_id,
        "mode": "hosted",
        "state": NOT_LINKED,
        "region": settings.fly_region,
        "token_hash": hash_secret(token),
    }
    runtime_id = (await conn.execute(insert(Rrotor).values(**values).returning(Rrotor.id))).scalar_one()
    await ensure_doorman(fly, settings)
    name = f"rt-{runtime_id.hex[:12]}"
    volume_id = await fly.create_volume(f"data_{runtime_id.hex[:12]}")
    machine_id = await fly.create_machine(name, volume_id, machine_env(settings, runtime_id, token))
    stamped = update(Rrotor).where(Rrotor.id == runtime_id).values(fly_machine_id=machine_id, fly_volume_id=volume_id)
    await conn.execute(stamped)
    log.info("hosted runtime provisioned", extra=fields(runtime=str(runtime_id), machine=machine_id))
    return runtime_id


async def start_hosted(conn: AsyncConnection, fly: Fly, settings: Settings, who: Principal) -> HostedRuntime:
    """The person's hosted runtime, made the first time, its machine started. Every plan has one; the plan's hours
    say how long it runs a month."""
    await conn.execute(select(User.id).where(User.id == who.user_id).with_for_update())
    mine = select(Rrotor.id, Rrotor.fly_machine_id, Rrotor.state).where(
        Rrotor.user_id == who.user_id, Rrotor.mode == "hosted"
    )
    row = (await conn.execute(mine)).first()
    if row is None:
        runtime_id = await _provision(conn, fly, settings, who)
        machine_id = (await conn.execute(select(Rrotor.fly_machine_id).where(Rrotor.id == runtime_id))).scalar_one()
    else:
        runtime_id, machine_id = row.id, row.fly_machine_id
    if row is None or row.state != ONLINE:
        await fly.start(str(machine_id))
    return await hosted_view(conn, who, settings.fly_public_domain)


async def stop_hosted(conn: AsyncConnection, fly: Fly, who: Principal, domain: str) -> HostedRuntime:
    """Stop the person's machine; a run in progress is left to the rrotor (it recovers it when next started)."""
    mine = select(Rrotor.id, Rrotor.fly_machine_id).where(Rrotor.user_id == who.user_id, Rrotor.mode == "hosted")
    row = (await conn.execute(mine)).first()
    if row is None:
        raise NotFound("You have no hosted runtime yet.", reason="no_runtime")
    await fly.stop(str(row.fly_machine_id))
    await conn.execute(update(Rrotor).where(Rrotor.id == row.id).values(state=NOT_LINKED))
    return await hosted_view(conn, who, domain)


async def destroy_hosted(conn: AsyncConnection, fly: Fly, who: Principal) -> None:
    """The machine, the volume and everything on it go; the runtime row with them. Not undone."""
    mine = select(Rrotor.id, Rrotor.fly_machine_id, Rrotor.fly_volume_id).where(
        Rrotor.user_id == who.user_id, Rrotor.mode == "hosted"
    )
    row = (await conn.execute(mine)).first()
    if row is None:
        raise NotFound("You have no hosted runtime yet.", reason="no_runtime")
    await fly.destroy(str(row.fly_machine_id), row.fly_volume_id)
    await conn.execute(delete(Rrotor).where(Rrotor.id == row.id))


def waker(engine: AsyncEngine, fly: Fly) -> Callable[[uuid.UUID], Awaitable[None]]:
    """The hub's waker: start the hosted runtime's machine when it is not online. Fly's start of a running machine
    is a no-op, so a stale `offline` costs nothing."""

    async def wake(runtime_id: uuid.UUID) -> None:
        async with engine.connect() as conn:
            found = select(Rrotor.fly_machine_id, Rrotor.state).where(Rrotor.id == runtime_id, Rrotor.mode == "hosted")
            row = (await conn.execute(found)).first()
        if row is None or row.fly_machine_id is None:
            raise Conflict("This runtime has no machine to wake.", runtime_id=str(runtime_id))
        if row.state != ONLINE:
            log.info("waking hosted runtime", extra=fields(runtime=str(runtime_id), machine=row.fly_machine_id))
            await fly.start(str(row.fly_machine_id))

    return wake


async def idle_hosted(engine: AsyncEngine, idle: timedelta) -> list[tuple[uuid.UUID, uuid.UUID, str]]:
    """Hosted runtimes online with no run in progress and none that started or ended within `idle`: each one's id,
    org and machine. A runtime that never ran counts from when it was last seen."""
    cutoff = datetime.now(UTC) - idle
    busy = select(Run.rrotor_id).where(Run.status.in_((RUNNING, *WAITING)))
    recent = select(Run.rrotor_id).where(func.coalesce(Run.ended_at, Run.started_at) >= cutoff)
    found = (
        select(Rrotor.id, User.org_id, Rrotor.fly_machine_id)
        .join(User, User.id == Rrotor.user_id)
        .where(
            Rrotor.mode == "hosted",
            Rrotor.state == ONLINE,
            Rrotor.fly_machine_id.is_not(None),
            Rrotor.last_seen_at < cutoff,
            Rrotor.id.not_in(busy),
            Rrotor.id.not_in(recent),
        )
    )
    async with engine.connect() as conn:  # the connecting role: every org's runtimes
        return [(r.id, r.org_id, str(r.fly_machine_id)) for r in await conn.execute(found)]


async def stop_idle(engine: AsyncEngine, fly: Fly, idle: timedelta) -> int:
    """Stop every idle hosted runtime; its rrotor's link closes, marking it offline, and a call wakes it again."""
    stopped = 0
    for runtime_id, org_id, machine_id in await idle_hosted(engine, idle):
        try:
            await fly.stop(machine_id)
        except Exception:
            log.exception("idle runtime not stopped", extra=fields(runtime=str(runtime_id)))
            continue
        async with engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            await conn.execute(update(Rrotor).where(Rrotor.id == runtime_id).values(state=NOT_LINKED))
        stopped += 1
    return stopped
