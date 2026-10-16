"""Runs: call a model on your runtime, answer or cancel a run, and read what became of it."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import runs
from glyphh_server.ops.link.protocol import Caller as Who
from glyphh_server.ops.link.protocol import Name
from glyphh_server.ops.runs import PAGE, RunView

router = APIRouter(prefix="/v1/runs", tags=["runs"])


class NewRun(BaseModel):
    model: Name
    function: Name = "start"
    inputs: dict[str, Any] = {}
    version: int | None = Field(None, ge=1, description="A version of the model; default the one active on the runtime")
    runtime_id: uuid.UUID | None = Field(
        None, description="One of your runtimes; default this install's, else the latest seen"
    )
    caller: Who = "claude"
    clearance: float = Field(1.0, ge=0, le=1, description="Who asks, 0 to 1: the model's ctx.clearance; 1 is you")


class AnswerBody(BaseModel):
    answer: Any = None


@router.get("", operation_id="listRuns")
async def list_runs(
    caller: Caller,
    conn: Conn,
    model: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = PAGE,
    before: Annotated[datetime | None, Query(description="Runs started before this: the previous page's last")] = None,
) -> list[RunView]:
    """Your runs, newest first."""
    return await runs.list_runs(conn, caller, model, status, limit, before)


@router.post("", operation_id="startRun", status_code=201)
async def start_run(body: NewRun, caller: Caller, conn: Conn, request: Request) -> RunView:
    """Call a function of your model: the run is `running` once the call went down the runtime's link; its result
    comes back on the link, so read the run again. A runtime not connected is E_UNAVAILABLE and nothing is kept."""
    hub = request.app.state.hub
    return await runs.start_run(
        conn,
        hub,
        caller,
        body.model,
        body.function,
        body.inputs,
        body.version,
        body.runtime_id,
        body.caller,
        body.clearance,
    )


@router.get("/{run_id}", operation_id="getRun")
async def get_run(run_id: uuid.UUID, caller: Caller, conn: Conn) -> RunView:
    return await runs.get_run(conn, caller, run_id)


@router.post("/{run_id}/continue", operation_id="continueRun")
async def continue_run(run_id: uuid.UUID, body: AnswerBody, caller: Caller, conn: Conn, request: Request) -> RunView:
    """Answer a run waiting for input; a run not waiting is E_CONFLICT."""
    return await runs.continue_run(conn, request.app.state.hub, caller, run_id, body.answer)


@router.post("/{run_id}/cancel", operation_id="cancelRun")
async def cancel_run(run_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> RunView:
    """Stop a run that has not ended; the rrotor answers `cancelled` once the model's `end` ran."""
    return await runs.cancel_run(conn, request.app.state.hub, caller, run_id)
