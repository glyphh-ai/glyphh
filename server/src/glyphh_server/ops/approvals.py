"""Approvals, shown in Claude: a run's step that needs the person is a row in `approvals` (the record, kept until
answered) and a signal on Redis to whichever server process holds the person's stream. The first answer wins.

Each person has one channel, and every event on it is one of two: `approval` {id, model, step, prompt, asked_at}
when a step starts waiting, and `answered` {id, answer} when it is answered anywhere, so the band clears in every
open Claude. Both are published as the transaction's last step."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import Select, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.signals import publish
from glyphh_server.errors import Conflict, NotFound, Unavailable
from glyphh_server.models import Approval, Model, ModelVersion, Run
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.link.calls import send_continue
from glyphh_server.ops.link.hub import Hub

Answer = Literal["approve", "decline"]


class ApprovalView(BaseModel):
    id: uuid.UUID
    model: str
    step: str
    prompt: str
    asked_at: datetime


class Answered(BaseModel):
    id: uuid.UUID
    answer: Answer


class Asked(BaseModel):
    approval: ApprovalView
    watched: bool  # whether a Claude was open to hear it; when not, the person is to be emailed


def channel(user_id: uuid.UUID) -> str:
    """The person's own channel: every server process holding one of their streams listens on it."""
    return f"approvals:{user_id}"


def _owned() -> Select:
    """Approvals joined to the model they wait in, and the model's owner, who is the one to answer."""
    return (
        select(Approval)
        .join(Run, Run.id == Approval.run_id)
        .join(ModelVersion, ModelVersion.id == Run.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
    )


async def waiting(conn: AsyncConnection, user_id: uuid.UUID) -> list[ApprovalView]:
    """The person's approvals not yet answered, newest first."""
    query = (
        _owned()
        .with_only_columns(Approval.id, Model.name.label("model"), Approval.step, Approval.prompt, Approval.asked_at)
        .where(Model.user_id == user_id, Approval.answer.is_(None))
        .order_by(Approval.asked_at.desc(), Approval.id.desc())
    )
    return [ApprovalView(**r._mapping) for r in await conn.execute(query)]


async def ask_approval(conn: AsyncConnection, redis: Redis, run_id: uuid.UUID, step: str, prompt: str) -> Asked:
    """A run answered needs_approval: keep the step waiting and signal the person's open Claudes. The entry point
    for the runtime's link (/v1/runtime/link) when a run stops at a step that needs approval."""
    owner = (
        select(Model.user_id, Model.name)
        .join(ModelVersion, ModelVersion.model_id == Model.id)
        .join(Run, Run.model_version_id == ModelVersion.id)
        .where(Run.id == run_id)
    )
    found = (await conn.execute(owner)).first()
    if found is None:
        raise NotFound("There is no such run.", run_id=str(run_id))
    made = insert(Approval).values(run_id=run_id, step=step, prompt=prompt).returning(Approval.id, Approval.asked_at)
    row = (await conn.execute(made)).one()
    view = ApprovalView(id=row.id, model=found.name, step=step, prompt=prompt, asked_at=row.asked_at)
    heard = await publish(redis, channel(found.user_id), "approval", view.model_dump(mode="json"))
    return Asked(approval=view, watched=heard > 0)


async def answer_approval(
    conn: AsyncConnection, redis: Redis, hub: Hub, who: Principal, approval_id: uuid.UUID, answer: Answer
) -> Answered:
    """The first answer wins: the row is locked, a second answer finds it answered. The run is handed back to its
    runtime, and every open Claude of the person's hears it was answered. A runtime that is not connected refuses it
    (E_UNAVAILABLE) and nothing is kept, so the person can answer again once it is back."""
    mine = _owned().where(Approval.id == approval_id, Model.user_id == who.user_id)
    locked = mine.with_only_columns(Approval.run_id, Approval.answer).with_for_update(of=Approval)
    row = (await conn.execute(locked)).first()
    if row is None:
        raise NotFound("You have no such approval.", approval_id=str(approval_id))
    if row.answer is not None:
        raise Conflict("This approval was already answered.", approval_id=str(approval_id), answer=row.answer)
    done = update(Approval).where(Approval.id == approval_id).values(answer=answer, answered_at=func.now())
    await conn.execute(done)
    await continue_run(conn, hub, row.run_id, approved=answer == "approve")
    answered = Answered(id=approval_id, answer=answer)
    await publish(redis, channel(who.user_id), "answered", answered.model_dump(mode="json"))
    return answered


async def continue_run(conn: AsyncConnection, hub: Hub, run_id: uuid.UUID, approved: bool) -> None:
    """The hand-off to the runtime: `continue {run_id, answer: {approved}}` goes down the runtime's link."""
    await send_continue(conn, hub, run_id, {"approved": approved})


async def email_approval(conn: AsyncConnection, approval_id: uuid.UUID) -> None:
    """Email the person a waiting step with an Approve link when no Claude is open, and stamp `notified_at`.

    Not built: no mail provider is configured in this repo. This is the seam the email plugs into; nothing calls it
    yet (ask_approval says whether a Claude heard the step: `watched`)."""
    raise Unavailable("Approval email is not built: no mail provider is configured.", approval_id=str(approval_id))
