"""Runs: a call of a person's model, sent down their runtime's link, and what became of it. The server keeps who
called, the status and the times, never inputs, outputs or content; the result comes back on the link, so a run just
started is `running` until the rrotor answers, and the caller asks again (or the mod reads the rrotor itself).

A call carries the caller's clearance (0 to 1, 1 the person themself): the model's `ctx.clearance`, never from the
inputs."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Model, ModelVersion, Run
from glyphh_server.ops import models
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.link.calls import send_call, send_cancel, send_continue
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.runtimes import runtime_for

PAGE: int = 50


class RunView(BaseModel):
    id: uuid.UUID
    model: str
    version: int
    function: str
    caller: str
    status: str = Field(description="running, needs_input, needs_approval, done, failed, expired or cancelled")
    runtime_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    seconds: int | None


def _owned(who: Principal) -> Select:
    return (
        select(
            Run.id,
            Model.name.label("model"),
            ModelVersion.version,
            Run.function,
            Run.caller,
            Run.status,
            Run.rrotor_id.label("runtime_id"),
            Run.started_at,
            Run.ended_at,
            Run.seconds,
        )
        .join(ModelVersion, ModelVersion.id == Run.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .where(Model.user_id == who.user_id)
    )


async def get_run(conn: AsyncConnection, who: Principal, run_id: uuid.UUID) -> RunView:
    row = (await conn.execute(_owned(who).where(Run.id == run_id))).first()
    if row is None:
        raise NotFound("You have no such run.", run_id=str(run_id))
    return RunView(**row._mapping)


async def list_runs(
    conn: AsyncConnection,
    who: Principal,
    model: str | None = None,
    status: str | None = None,
    limit: int = PAGE,
    before: datetime | None = None,
) -> list[RunView]:
    """The person's runs, newest first; `before` (a run's started_at) pages further back."""
    query = _owned(who)
    if model is not None:
        query = query.where(Model.name == model)
    if status is not None:
        query = query.where(Run.status == status)
    if before is not None:
        query = query.where(Run.started_at < before)
    rows = await conn.execute(query.order_by(Run.started_at.desc(), Run.id.desc()).limit(limit))
    return [RunView(**r._mapping) for r in rows]


async def start_run(
    conn: AsyncConnection,
    hub: Hub,
    who: Principal,
    model: str,
    function: str,
    inputs: dict[str, Any],
    version: int | None,
    runtime_id: uuid.UUID | None,
    caller: str,
    clearance: float,
) -> RunView:
    """Call a function of the person's model on their runtime: the run, `running`, once the call went down the link."""
    model_id = await models.by_name(conn, who, model)
    runtime = await runtime_for(conn, who, runtime_id)
    run_id = await send_call(conn, hub, runtime, model_id, version, function, inputs, caller, clearance)
    return await get_run(conn, who, run_id)


async def continue_run(conn: AsyncConnection, hub: Hub, who: Principal, run_id: uuid.UUID, answer: Any) -> RunView:
    """Answer a run waiting for input (or an approval, as the approvals API does): it runs again."""
    await get_run(conn, who, run_id)
    await send_continue(conn, hub, run_id, answer)
    return await get_run(conn, who, run_id)


async def cancel_run(conn: AsyncConnection, hub: Hub, who: Principal, run_id: uuid.UUID) -> RunView:
    """Stop a run: the rrotor runs the model's `end` and answers `cancelled`; until then the run is as it was."""
    await get_run(conn, who, run_id)
    await send_cancel(conn, hub, run_id)
    return await get_run(conn, who, run_id)
