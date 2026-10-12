"""A thread as every view shows it: its record, who works it, and how many questions are waiting. Never its
messages: those are on the machine."""

import uuid
from collections import defaultdict
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import aliased

from glyphh_server.errors import NotFound
from glyphh_server.models import NeedsYou, SuperPower, Thread, ThreadCrew
from glyphh_server.ops.auth.principal import Principal


class CrewFace(BaseModel):
    """A super power as a thread shows it: its face and its name."""

    id: uuid.UUID
    name: str
    avatar_variant: int
    avatar_color: str | None


class ThreadRow(BaseModel):
    id: uuid.UUID
    machine_id: uuid.UUID
    goal: str
    status: str
    last_seq: int
    last_event_at: datetime
    pinned_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    super_power: CrewFace | None
    crew: list[CrewFace]
    needs_you: int


Solo = aliased(SuperPower)
SOLO = (
    Solo.id.label("sp_id"),
    Solo.name.label("sp_name"),
    Solo.avatar_variant.label("sp_variant"),
    Solo.avatar_color.label("sp_color"),
)
RECORD = (
    Thread.id,
    Thread.machine_id,
    Thread.goal,
    Thread.status,
    Thread.last_seq,
    Thread.last_event_at,
    Thread.pinned_at,
    Thread.archived_at,
    Thread.created_at,
    *SOLO,
)


def mine(who: Principal):  # type: ignore[no-untyped-def]
    """The caller's own threads, in the org they act in."""
    return (Thread.user_id == who.user_id, Thread.org_id == who.org_id)


def records():  # type: ignore[no-untyped-def]
    return select(*RECORD).outerjoin(Solo, Solo.id == Thread.super_power_id)


async def rows(conn: AsyncConnection, found: list) -> list[ThreadRow]:  # type: ignore[type-arg]
    """Each record with its crew and its open questions, in two more queries for the whole page."""
    ids = [r.id for r in found]
    crews: dict[uuid.UUID, list[CrewFace]] = defaultdict(list)
    crew_q = (
        select(ThreadCrew.thread_id, SuperPower.id, SuperPower.name, SuperPower.avatar_variant, SuperPower.avatar_color)
        .join(SuperPower, SuperPower.id == ThreadCrew.super_power_id)
        .where(ThreadCrew.thread_id.in_(ids))
        .order_by(ThreadCrew.added_at, SuperPower.name)
    )
    for r in await conn.execute(crew_q):
        crews[r.thread_id].append(
            CrewFace(id=r.id, name=r.name, avatar_variant=r.avatar_variant, avatar_color=r.avatar_color)
        )
    open_q = (
        select(NeedsYou.thread_id, func.count())
        .where(NeedsYou.thread_id.in_(ids), NeedsYou.answer.is_(None))
        .group_by(NeedsYou.thread_id)
    )
    waiting = {r[0]: r[1] for r in await conn.execute(open_q)}
    return [_row(r, crews[r.id], waiting.get(r.id, 0)) for r in found]


def _row(r, crew: list[CrewFace], needs_you: int) -> ThreadRow:  # type: ignore[no-untyped-def]
    solo = (
        None
        if r.sp_id is None
        else CrewFace(id=r.sp_id, name=r.sp_name, avatar_variant=r.sp_variant, avatar_color=r.sp_color)
    )
    record = {
        k: getattr(r, k)
        for k in (
            "id",
            "machine_id",
            "goal",
            "status",
            "last_seq",
            "last_event_at",
            "pinned_at",
            "archived_at",
            "created_at",
        )
    }
    return ThreadRow(**record, super_power=solo, crew=crew, needs_you=needs_you)


async def my_thread(conn: AsyncConnection, who: Principal, thread_id: uuid.UUID) -> ThreadRow:
    found = (await conn.execute(records().where(Thread.id == thread_id, *mine(who)))).all()
    if not found:
        raise NotFound("No such thread of yours.")
    return (await rows(conn, found))[0]
