"""Needs you: every question a member's super powers are waiting on, across their machines, newest first; and
answering one, once (two answers at the same moment: the first wins, the second is told). Sending the answer to
the machine arrives with the machine link."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Machine, NeedsYou, SuperPower, Thread
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.threads.shape import CrewFace


class Question(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    thread_goal: str
    machine_id: uuid.UUID
    machine_name: str
    super_power: CrewFace | None
    kind: str
    tool: str
    detail: str
    asked_at: datetime


class QuestionPage(BaseModel):
    questions: list[Question]
    total: int


class Answered(BaseModel):
    id: uuid.UUID
    answer: Literal["allow", "deny"]
    answered_at: datetime


COLS = (
    NeedsYou.id,
    NeedsYou.thread_id,
    Thread.goal,
    Thread.machine_id,
    Machine.name.label("machine_name"),
    SuperPower.id.label("sp_id"),
    SuperPower.name.label("sp_name"),
    SuperPower.avatar_variant,
    SuperPower.avatar_color,
    NeedsYou.kind,
    NeedsYou.tool,
    NeedsYou.detail,
    NeedsYou.asked_at,
)


def _question(r) -> Question:  # type: ignore[no-untyped-def]
    face = (
        None
        if r.sp_id is None
        else CrewFace(id=r.sp_id, name=r.sp_name, avatar_variant=r.avatar_variant, avatar_color=r.avatar_color)
    )
    return Question(
        id=r.id,
        thread_id=r.thread_id,
        thread_goal=r.goal,
        machine_id=r.machine_id,
        machine_name=r.machine_name,
        super_power=face,
        kind=r.kind,
        tool=r.tool,
        detail=r.detail,
        asked_at=r.asked_at,
    )


async def open_questions(
    conn: AsyncConnection, who: Principal, page: int = 1, size: int = 100, thread_id: uuid.UUID | None = None
) -> QuestionPage:
    where = [NeedsYou.user_id == who.user_id, NeedsYou.org_id == who.org_id, NeedsYou.answer.is_(None)]
    if thread_id:
        where.append(NeedsYou.thread_id == thread_id)
    q = (
        select(*COLS)
        .join(Thread, Thread.id == NeedsYou.thread_id)
        .join(Machine, Machine.id == Thread.machine_id)
        .outerjoin(SuperPower, SuperPower.id == NeedsYou.super_power_id)
        .where(*where)
    )
    found = await conn.execute(q.order_by(NeedsYou.asked_at.desc(), NeedsYou.id).offset((page - 1) * size).limit(size))
    total = (await conn.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    return QuestionPage(questions=[_question(r) for r in found], total=total)


async def answer(conn: AsyncConnection, who: Principal, question_id: uuid.UUID, allow: bool) -> Answered:
    mine = (NeedsYou.id == question_id, NeedsYou.user_id == who.user_id, NeedsYou.org_id == who.org_id)
    given = "allow" if allow else "deny"
    done = await conn.execute(
        update(NeedsYou)
        .where(*mine, NeedsYou.answer.is_(None))
        .values(answer=given, answered_by=who.user_id, answered_at=func.now())
        .returning(NeedsYou.id, NeedsYou.answer, NeedsYou.answered_at)
    )
    row = done.first()
    if row is not None:
        return Answered(id=row.id, answer=row.answer, answered_at=row.answered_at)
    before = (await conn.execute(select(NeedsYou.answer).where(*mine))).first()
    if before is None:
        raise NotFound("No such question for you.")
    raise Conflict(f"Already answered: {before.answer}.", reason="answered", answer=before.answer)
