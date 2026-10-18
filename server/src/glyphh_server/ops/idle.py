"""Hosted machines left alone: the hub's waker starts a stopped one when a call is for it, and the server's minute
tick stops each one that sat idle. Both act on one machine at a time; a person's other machines are untouched."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict
from glyphh_server.models import Rrotor, Run, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.link.protocol import RUNNING, WAITING
from glyphh_server.ops.runtimes import NOT_LINKED

log = logging.getLogger("glyphh.runtime")


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
