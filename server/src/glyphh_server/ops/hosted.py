"""Hosted runtimes on Fly: each a machine and its volume, of the size the person chose (ops/machines.py makes, starts,
stops, restarts and deletes them, up to the plan's machines). The runtime token goes into the machine's environment
(nobody signs in on it); its licence and its keys come in its welcome. It is reached at its own address,
`https://<machine>.<domain>`, through Fly's proxy: a request starts a stopped machine, and the doorman machine (one
per app, made with the first runtime) replays a request that landed elsewhere. The server stops a machine that sat
idle (ops/idle.py) and those held past the plan (ops/held.py), and meters each machine per second at Fly's rates, its
online time this month tallied (ops/metering.py, the minute tick in ops/tend.py); no plan has hours, so a machine is
never paused. `state` is `stopped` until its hello, `online` while linked, `offline` after a link dropped.

All of it is behind GLYPHH_HOSTING, off by default (require_hosting): off, no machine is made, started or woken."""

import logging
import uuid

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.models import Rrotor
from glyphh_server.models.rrotor import SIZES, SizeName
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.runtimes import NOT_LINKED

log = logging.getLogger("glyphh.runtime")

DOORMAN: str = "doorman"
HOSTING_OFF: str = "Glyphh's managed cloud is off: run rrotor yourself and register it (a self-hosted runtime)."


def require_hosting(settings: Settings) -> None:
    """Refused unless GLYPHH_HOSTING is on: E_UNAVAILABLE `hosting_off`, as for a server without Fly."""
    if not settings.hosting:
        raise Unavailable(HOSTING_OFF, reason="hosting_off")


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
    machine_id = await fly.create_machine(DOORMAN, None, env)
    await fly.start(machine_id)
    log.info("doorman made", extra=fields(machine=machine_id))
    return machine_id


async def provision(conn: AsyncConnection, fly: Fly, who: Principal, name: str, size: SizeName) -> uuid.UUID:
    """A machine and its volume of that size, and the runtime row they belong to; the token is only ever in the
    machine. Made stopped (Fly's skip_launch)."""
    settings, token = fly.settings, make_secret()
    values = {
        "user_id": who.user_id,
        "mode": "hosted",
        "name": name,
        "size": size,
        "state": NOT_LINKED,
        "region": settings.fly_region,
        "token_hash": hash_secret(token),
    }
    runtime_id = (await conn.execute(insert(Rrotor).values(**values).returning(Rrotor.id))).scalar_one()
    await ensure_doorman(fly, settings)
    volume_id = await fly.create_volume(f"data_{runtime_id.hex[:12]}", SIZES[size])
    env = machine_env(settings, runtime_id, token)
    machine_id = await fly.create_machine(f"rt-{runtime_id.hex[:12]}", volume_id, env, SIZES[size])
    stamped = update(Rrotor).where(Rrotor.id == runtime_id).values(fly_machine_id=machine_id, fly_volume_id=volume_id)
    await conn.execute(stamped)
    log.info("hosted runtime provisioned", extra=fields(runtime=str(runtime_id), machine=machine_id))
    return runtime_id
