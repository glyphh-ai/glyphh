"""The org's programs (docs/specs/programs.md): each a `program.py` whose steps are its bots' tools, its bots, the
person's answers, branches and code; run here by the server, its code steps on its rrotor; run by a person, its
schedule or the connector, every step of every run a line of its audit trail. And `search_tool`: the tools a bot or a
program could use, and one added to a bot. Each route takes a person's Ada API key too (api/key_auth.py)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.key_auth import KeyCaller as Caller
from glyphh_server.api.key_auth import KeyPerson as Person
from glyphh_server.ops.programs import events, found, runs, store
from glyphh_server.ops.programs.views import (
    AddToolIn,
    AnswerIn,
    Events,
    FoundTools,
    ProgramIn,
    ProgramPatch,
    ProgramRuns,
    ProgramRunView,
    Programs,
    ProgramView,
    RunIn,
)

router = APIRouter(tags=["programs"])


def _programs(request: Request) -> Any:
    return request.app.state.bots.programs


@router.get("/v1/programs", operation_id="listPrograms")
async def list_programs(
    caller: Caller, conn: Conn, q: Annotated[str, Query(max_length=200, description="Words it has")] = ""
) -> Programs:
    return Programs(programs=await store.listed(conn, q))


@router.post("/v1/programs", operation_id="createProgram", status_code=201)
async def create_program(body: ProgramIn, caller: Caller, conn: Conn) -> ProgramView:
    """A program, from its file or its steps (written into a new file); kept even while its steps cannot run yet,
    each problem said."""
    return await store.create(conn, caller, body)


@router.get("/v1/programs/{slug}", operation_id="getProgram")
async def get_program(slug: str, caller: Caller, conn: Conn) -> ProgramView:
    return await store.view(conn, await store.row(conn, slug))


@router.patch("/v1/programs/{slug}", operation_id="updateProgram")
async def update_program(slug: str, body: ProgramPatch, caller: Caller, conn: Conn) -> ProgramView:
    """What is given changed: `flow` rewrites the file's FLOW in place, `source` replaces the file (not both)."""
    return await store.patch(conn, slug, body)


@router.delete("/v1/programs/{slug}", operation_id="deleteProgram", status_code=204)
async def delete_program(slug: str, caller: Caller, conn: Conn) -> Response:
    await store.remove(conn, slug)
    return Response(status_code=204)


@router.post("/v1/programs/{slug}/runs", operation_id="runProgram", status_code=202)
async def run_program(slug: str, body: RunIn, request: Request, who: Person) -> ProgramRunView:
    """A run, queued (422 while its steps cannot run; 409 while its last run is live)."""
    return await _programs(request).start(who, slug, body.input)


@router.get("/v1/programs/{slug}/runs", operation_id="listProgramRuns")
async def list_runs(slug: str, caller: Caller, conn: Conn) -> ProgramRuns:
    return ProgramRuns(runs=await runs.listed(conn, await store.row(conn, slug)))


@router.get("/v1/program-runs/{run_id}", operation_id="getProgramRun")
async def get_run(run_id: uuid.UUID, caller: Caller, conn: Conn) -> ProgramRunView:
    return runs.view(await runs.row(conn, run_id))


@router.get("/v1/program-runs/{run_id}/events", operation_id="listProgramRunEvents")
async def list_events(
    run_id: uuid.UUID, caller: Caller, conn: Conn, after: Annotated[int, Query(ge=0, description="After this n")] = 0
) -> Events:
    """The run's audit trail from `after` on: each step, question, answer and end, with the bot that did it and the
    person who started or answered it."""
    await runs.row(conn, run_id)
    return Events(events=await events.read(conn, run_id, after))


@router.post("/v1/program-runs/{run_id}/answer", operation_id="answerProgramRun", status_code=202)
async def answer_run(run_id: uuid.UUID, body: AnswerIn, request: Request, who: Person) -> ProgramRunView:
    return await _programs(request).answer(who, run_id, body.answer)


@router.post("/v1/program-runs/{run_id}/cancel", operation_id="cancelProgramRun")
async def cancel_run(run_id: uuid.UUID, request: Request, who: Person) -> ProgramRunView:
    return await _programs(request).cancel(who, run_id)


@router.get("/v1/tools/search", operation_id="searchTools")
async def search_tools(
    request: Request,
    who: Caller,
    q: Annotated[str, Query(max_length=200, description="Words the tool has")] = "",
    bot: Annotated[str | None, Query(max_length=80, description="A bot's slug: whether it has each")] = None,
) -> FoundTools:
    """Tools of the org's connected apps, and Glyphh's built-ins, whose words have every word of `q`."""
    svc = request.app.state.bots
    return FoundTools(tools=await found.search(svc.pd, svc.engine, who, q, bot))


@router.post("/v1/bots/{slug}/tools", operation_id="addBotTool", status_code=204)
async def add_tool(slug: str, body: AddToolIn, request: Request, who: Caller) -> Response:
    """A found tool given to the bot (a connection's, or a built-in with no connection)."""
    svc = request.app.state.bots
    await found.add(svc.pd, svc.engine, who, slug, body)
    return Response(status_code=204)
