"""A machine's threads, as Recents lists them: pinned first, then the newest; searched by goal, narrowed to the
threads a super power is in, archived or not, a page at a time; with every super power in them and how many
threads each is in, for the filter. What was said is searched on the machine, not here."""

import uuid

from pydantic import BaseModel
from sqlalchemy import exists, func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import SuperPower, Thread, ThreadCrew
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.machines.installed import machine_named
from glyphh_server.ops.threads.shape import CrewFace, ThreadRow, mine, records, rows


class CrewCount(BaseModel):
    super_power: CrewFace
    threads: int


class ThreadPage(BaseModel):
    machine: str
    threads: list[ThreadRow]
    total: int
    crew: list[CrewCount]


def _where(who: Principal, machine_id: uuid.UUID, archived: bool):  # type: ignore[no-untyped-def]
    archive = Thread.archived_at.is_not(None) if archived else Thread.archived_at.is_(None)
    return (Thread.machine_id == machine_id, archive, *mine(who))


def _in(super_power: uuid.UUID):  # type: ignore[no-untyped-def]
    in_crew = exists().where(ThreadCrew.thread_id == Thread.id, ThreadCrew.super_power_id == super_power)
    return or_(Thread.super_power_id == super_power, in_crew)


async def _crew(conn: AsyncConnection, base) -> list[CrewCount]:  # type: ignore[no-untyped-def]
    solo = select(Thread.id.label("t"), Thread.super_power_id.label("sp")).where(
        *base, Thread.super_power_id.is_not(None)
    )
    crew = (
        select(ThreadCrew.thread_id, ThreadCrew.super_power_id)
        .join(Thread, Thread.id == ThreadCrew.thread_id)
        .where(*base)
    )
    members = union_all(solo, crew).subquery()
    face = (SuperPower.id, SuperPower.name, SuperPower.avatar_variant, SuperPower.avatar_color)
    q = (
        select(*face, func.count(func.distinct(members.c.t)).label("n"))
        .join(members, members.c.sp == SuperPower.id)
        .group_by(*face)
        .order_by(SuperPower.name)
    )
    return [
        CrewCount(
            super_power=CrewFace(id=r.id, name=r.name, avatar_variant=r.avatar_variant, avatar_color=r.avatar_color),
            threads=r.n,
        )
        for r in await conn.execute(q)
    ]


async def list_threads(
    conn: AsyncConnection,
    who: Principal,
    machine_id: uuid.UUID,
    q: str,
    super_power: uuid.UUID | None,
    archived: bool,
    page: int,
    size: int,
) -> ThreadPage:
    machine = await machine_named(conn, who, machine_id)
    base = _where(who, machine_id, archived)
    where = list(base)
    if q:
        where.append(Thread.goal.ilike(f"%{q.replace('%', r'\%').replace('_', r'\_')}%"))
    if super_power:
        where.append(_in(super_power))
    picked = records().where(*where)
    order = (Thread.pinned_at.desc().nulls_last(), Thread.last_event_at.desc(), Thread.id)
    found = (await conn.execute(picked.order_by(*order).offset((page - 1) * size).limit(size))).all()
    total = (await conn.execute(select(func.count()).select_from(picked.subquery()))).scalar_one()
    return ThreadPage(machine=machine.name, threads=await rows(conn, found), total=total, crew=await _crew(conn, base))
