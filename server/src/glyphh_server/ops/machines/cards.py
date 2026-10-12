"""Your machines as cards: each with its 8 most recently active super powers and what they are doing, a page
at a time, connected ones first."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Machine, SuperPower, SuperPowerInstall
from glyphh_server.ops.auth.principal import Principal

ON_A_CARD: int = 8


class Face(BaseModel):
    """A super power as a machine shows it: its face, its name, what it is doing there."""

    id: uuid.UUID
    name: str
    description: str
    avatar_variant: int
    avatar_color: str | None
    status: str
    last_active_at: datetime | None


class MachineCard(BaseModel):
    id: uuid.UUID
    name: str
    host: str
    platform: str
    version: str
    online: bool
    last_seen_at: datetime | None
    super_powers: list[Face]
    installed: int
    working: int
    needs_you: int


class MachinePage(BaseModel):
    machines: list[MachineCard]
    total: int
    online: int


def mine(who: Principal):  # type: ignore[no-untyped-def]
    """The caller's own machines in the org they act in, not revoked."""
    return (Machine.user_id == who.user_id, Machine.org_id == who.org_id, Machine.revoked_at.is_(None))


FACE = (
    SuperPower.id,
    SuperPower.name,
    SuperPower.description,
    SuperPower.avatar_variant,
    SuperPower.avatar_color,
    SuperPowerInstall.status,
    SuperPowerInstall.last_active_at,
)
RECENT = (SuperPowerInstall.last_active_at.desc().nulls_last(), SuperPower.name)


async def _faces(conn: AsyncConnection, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Face]]:
    rank = func.row_number().over(partition_by=SuperPowerInstall.machine_id, order_by=RECENT).label("rank")
    ranked = (
        select(SuperPowerInstall.machine_id, *FACE, rank)
        .join(SuperPower, SuperPower.id == SuperPowerInstall.super_power_id)
        .where(SuperPowerInstall.machine_id.in_(ids))
        .subquery()
    )
    rows = await conn.execute(select(ranked).where(ranked.c.rank <= ON_A_CARD).order_by(ranked.c.rank))
    faces: dict[uuid.UUID, list[Face]] = {i: [] for i in ids}
    for r in rows:
        faces[r.machine_id].append(Face.model_validate(r, from_attributes=True))
    return faces


async def _counts(conn: AsyncConnection, ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int, int]]:
    status = SuperPowerInstall.status
    rows = await conn.execute(
        select(
            SuperPowerInstall.machine_id,
            func.count(),
            func.count().filter(status == "working"),
            func.count().filter(status == "needs_you"),
        )
        .where(SuperPowerInstall.machine_id.in_(ids))
        .group_by(SuperPowerInstall.machine_id)
    )
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


async def list_machines(conn: AsyncConnection, who: Principal, page: int, size: int) -> MachinePage:
    cols = (
        Machine.id,
        Machine.name,
        Machine.host,
        Machine.platform,
        Machine.version,
        Machine.online,
        Machine.last_seen_at,
    )
    rows = (
        await conn.execute(
            select(*cols)
            .where(*mine(who))
            .order_by(Machine.online.desc(), Machine.name)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    total, online = (
        await conn.execute(select(func.count(), func.count().filter(Machine.online)).where(*mine(who)))
    ).one()
    ids = [r.id for r in rows]
    faces, counts = await _faces(conn, ids), await _counts(conn, ids)
    cards = [
        MachineCard(
            **r._mapping,
            super_powers=faces[r.id],
            **dict(zip(("installed", "working", "needs_you"), counts.get(r.id, (0, 0, 0)), strict=True)),
        )
        for r in rows
    ]
    return MachinePage(machines=cards, total=total, online=online)
