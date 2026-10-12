"""Every super power on one of your machines (the See all dialog): searched by name or what it does, filtered by
what it is doing, a page at a time, the most recently active first; with how many there are of each status."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import STATUSES, Machine, SuperPower, SuperPowerInstall
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.machines.cards import FACE, RECENT, Face, mine


class InstalledPage(BaseModel):
    machine: str
    super_powers: list[Face]
    total: int
    counts: dict[str, int]


class Named(BaseModel):
    name: str
    online: bool
    last_seen_at: datetime | None


async def machine_named(conn: AsyncConnection, who: Principal, machine_id: uuid.UUID) -> Named:
    cols = (Machine.name, Machine.online, Machine.last_seen_at)
    row = (await conn.execute(select(*cols).where(Machine.id == machine_id, *mine(who)))).first()
    if row is None:
        raise NotFound("No such machine of yours.")
    return Named.model_validate(row, from_attributes=True)


async def _counts(conn: AsyncConnection, machine_id: uuid.UUID) -> dict[str, int]:
    rows = await conn.execute(
        select(SuperPowerInstall.status, func.count())
        .where(SuperPowerInstall.machine_id == machine_id)
        .group_by(SuperPowerInstall.status)
    )
    counts = {s: 0 for s in STATUSES} | {r[0]: r[1] for r in rows}
    return {"all": sum(counts.values()), **counts}


async def installed(
    conn: AsyncConnection, who: Principal, machine_id: uuid.UUID, q: str, status: str | None, page: int, size: int
) -> InstalledPage:
    machine = await machine_named(conn, who, machine_id)
    where = [SuperPowerInstall.machine_id == machine_id]
    if q:
        like = f"%{q.replace('%', r'\%').replace('_', r'\_')}%"
        where.append(or_(SuperPower.name.ilike(like), SuperPower.description.ilike(like)))
    if status:
        where.append(SuperPowerInstall.status == status)
    joined = select(*FACE).join(SuperPower, SuperPower.id == SuperPowerInstall.super_power_id).where(*where)
    rows = await conn.execute(joined.order_by(*RECENT).offset((page - 1) * size).limit(size))
    total = (await conn.execute(select(func.count()).select_from(joined.subquery()))).scalar_one()
    faces = [Face.model_validate(r, from_attributes=True) for r in rows]
    return InstalledPage(machine=machine.name, super_powers=faces, total=total, counts=await _counts(conn, machine_id))
