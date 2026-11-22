"""The org's swarms (docs/specs/bots.md, 10): a crew of its bots taking turns on one GitHub repo, on one of its rrotors,
each turn a pull request the person merges or rejects (or merged as it opens); the org's GitHub token the turns use.
And the bots' tool callback: a bot running on a rrotor calls its tools here, with its run's tool token."""

import uuid
from typing import Any

from fastapi import APIRouter, Request, Response

from glyphh_server.api.auth import Bearer, Caller, Cfg, Conn
from glyphh_server.api.templates import Person
from glyphh_server.errors import Unauthorized
from glyphh_server.ops.bots import remote_in, tool_calls
from glyphh_server.ops.swarms import github, runs, store
from glyphh_server.ops.swarms.views import (
    GitHubKeyIn,
    GitHubKeyView,
    ReviewIn,
    SwarmIn,
    SwarmPatch,
    SwarmRuns,
    SwarmRunView,
    Swarms,
    SwarmView,
    TaskIn,
)

router = APIRouter(tags=["swarms"])


def _swarms(request: Request) -> Any:
    return request.app.state.bots.swarms


@router.get("/v1/swarms", operation_id="listSwarms")
async def list_swarms(caller: Caller, conn: Conn) -> Swarms:
    return Swarms(swarms=await store.listing(conn))


@router.post("/v1/swarms", operation_id="createSwarm", status_code=201)
async def create_swarm(body: SwarmIn, caller: Caller, conn: Conn) -> SwarmView:
    """A swarm: its crew (the org's bots, in speaking order), repo, base branch, rounds, review, and its rrotor."""
    return await store.create(conn, caller, body)


@router.get("/v1/swarms/{slug}", operation_id="getSwarm")
async def get_swarm(slug: str, caller: Caller, conn: Conn) -> SwarmView:
    return await store.one(conn, slug)


@router.patch("/v1/swarms/{slug}", operation_id="updateSwarm")
async def update_swarm(slug: str, body: SwarmPatch, caller: Caller, conn: Conn) -> SwarmView:
    return await store.patch(conn, slug, body)


@router.delete("/v1/swarms/{slug}", operation_id="deleteSwarm", status_code=204)
async def delete_swarm(slug: str, caller: Caller, conn: Conn) -> Response:
    """The swarm deleted, with its runs (their pull requests stay on GitHub)."""
    await store.remove(conn, slug)
    return Response(status_code=204)


@router.post("/v1/swarms/{slug}/runs", operation_id="runSwarm", status_code=202)
async def run_swarm(slug: str, body: TaskIn, request: Request, who: Person) -> SwarmRunView:
    """A run of the swarm on a task: its first bot's turn sent to its rrotor (409 while one is live or the rrotor is
    offline; 404 github_key without the org's GitHub token)."""
    return await _swarms(request).start(who, slug, body.task)  # type: ignore[no-any-return]


@router.get("/v1/swarms/{slug}/runs", operation_id="listSwarmRuns")
async def list_swarm_runs(slug: str, caller: Caller, conn: Conn) -> SwarmRuns:
    """Its runs with their turns, the newest first (the last 50)."""
    return SwarmRuns(runs=await runs.listing(conn, await store.row(conn, slug)))


@router.get("/v1/swarm-runs/{run_id}", operation_id="getSwarmRun")
async def get_swarm_run(run_id: uuid.UUID, caller: Caller, conn: Conn) -> SwarmRunView:
    return await runs.get(conn, run_id)


@router.post("/v1/swarm-runs/{run_id}/answer", operation_id="answerSwarmRun", status_code=202)
async def answer_swarm_run(run_id: uuid.UUID, body: ReviewIn, request: Request, who: Person) -> SwarmRunView:
    """The pull request that waits, merged or rejected: then the next bot goes."""
    return await _swarms(request).answer(who, run_id, body.answer)  # type: ignore[no-any-return]


@router.post("/v1/swarm-runs/{run_id}/cancel", operation_id="cancelSwarmRun")
async def cancel_swarm_run(run_id: uuid.UUID, request: Request, who: Person) -> SwarmRunView:
    """The run ended; its turn out on the rrotor stopped (an open pull request stays open)."""
    return await _swarms(request).cancel(who, run_id)  # type: ignore[no-any-return]


@router.get("/v1/github-key", operation_id="getGitHubKey")
async def get_github_key(caller: Caller, conn: Conn) -> GitHubKeyView:
    return github.view(await github.get(conn))


@router.put("/v1/github-key", operation_id="setGitHubKey")
async def set_github_key(body: GitHubKeyIn, request: Request, who: Caller, conn: Conn, settings: Cfg) -> GitHubKeyView:
    """The org's GitHub token, tried with GitHub, then kept sealed: its swarms push and open pull requests with it."""
    return await github.put(conn, who, settings.secret_key, body.token, _swarms(request).check_github)


@router.delete("/v1/github-key", operation_id="removeGitHubKey")
async def remove_github_key(caller: Caller, conn: Conn) -> GitHubKeyView:
    return await github.remove(conn, caller.org_id)


@router.post("/v1/bots/runs/{run_id}/tool", operation_id="callBotTool")
async def call_bot_tool(run_id: uuid.UUID, body: tool_calls.ToolIn, request: Request, creds: Bearer) -> dict[str, Any]:
    """A bot running on a rrotor calls one of its tools (fetch, or a connection's): bearer its run's tool token;
    answered {"result": ...} or {"error": "..."}."""
    if creds is None:
        raise Unauthorized(remote_in.BAD_TOKEN)
    return await tool_calls.call(request.app.state.bots, creds.credentials, run_id, body)
