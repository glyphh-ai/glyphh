"""Opening a machine's UI: a ticket for one member and one machine, landing on one page, good for a minute and
once. rrotor checks it with the server, so a member signs in on the server, never on a machine."""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import LaunchTicket, SuperPowerInstall
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.machines.installed import machine_named

TICKET_TTL: timedelta = timedelta(minutes=1)


class Launch(BaseModel):
    url: str
    expires_at: datetime


async def _page(conn: AsyncConnection, machine_id: uuid.UUID, super_power: uuid.UUID | None) -> str:
    if super_power is None:
        return "home"
    there = select(SuperPowerInstall.super_power_id).where(
        SuperPowerInstall.machine_id == machine_id, SuperPowerInstall.super_power_id == super_power
    )
    if (await conn.execute(there)).first() is None:
        raise NotFound("That super power isn't installed on this machine.")
    return f"super_powers/{super_power}"


async def open_machine(
    conn: AsyncConnection, who: Principal, machine_id: uuid.UUID, super_power: uuid.UUID | None, domain: str
) -> Launch:
    machine = await machine_named(conn, who, machine_id)
    if not machine.online:
        raise Conflict(f"{machine.name} is offline.", reason="offline", last_seen_at=str(machine.last_seen_at))
    page = await _page(conn, machine_id, super_power)
    ticket, expires = make_secret(), datetime.now(UTC) + TICKET_TTL
    await conn.execute(
        insert(LaunchTicket).values(
            user_id=who.user_id, machine_id=machine_id, page=page, token_hash=hash_secret(ticket), expires_at=expires
        )
    )
    return Launch(url=f"https://{machine_id}.{domain}/open?ticket={ticket}", expires_at=expires)
