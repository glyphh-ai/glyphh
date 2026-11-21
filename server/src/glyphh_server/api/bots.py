"""The org's hosted bots (docs/specs/bots.md): made with a name, a look (its cat), instructions, the Claude model it
runs on and the Ada models it may ask; scoped per connection to the tools it may use; run in the background, each run's
steps, answer and tokens kept. A run's tokens are drawn from the plan's allowance, then the org's balance."""

import uuid
from typing import Any

from fastapi import APIRouter, Request, Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.templates import Person
from glyphh_server.ops.bots import prices, runs, store
from glyphh_server.ops.bots.prices import BotModels
from glyphh_server.ops.bots.views import BotIn, BotPatch, Bots, BotView, RunIn, Runs, RunView, ScopesIn

router = APIRouter(tags=["bots"])


@router.get("/v1/bots", operation_id="listBots")
async def list_bots(caller: Caller, conn: Conn) -> Bots:
    return Bots(bots=await store.listing(conn))


@router.get("/v1/bots/models", operation_id="listBotModels")
async def list_models(caller: Caller) -> BotModels:
    """The Claude models a bot may run on, at their rates."""
    return prices.listing()


@router.post("/v1/bots", operation_id="createBot", status_code=201)
async def create_bot(body: BotIn, caller: Caller, conn: Conn) -> BotView:
    """A bot; its slug comes from its name (another bot of the org's with that slug: 409 E_CONFLICT)."""
    return await store.create(conn, caller, body)


@router.get("/v1/bots/{slug}", operation_id="getBot")
async def get_bot(slug: str, caller: Caller, conn: Conn) -> BotView:
    return await store.one(conn, slug)


@router.patch("/v1/bots/{slug}", operation_id="updateBot")
async def update_bot(slug: str, body: BotPatch, caller: Caller, conn: Conn) -> BotView:
    """What is given changed; a new name changes the slug."""
    return await store.patch(conn, slug, body)


@router.delete("/v1/bots/{slug}", operation_id="deleteBot", status_code=204)
async def delete_bot(slug: str, caller: Caller, conn: Conn) -> Response:
    """The bot deleted, with its runs."""
    await store.remove(conn, slug)
    return Response(status_code=204)


@router.put("/v1/bots/{slug}/connections", operation_id="setBotConnections")
async def set_connections(slug: str, body: ScopesIn, caller: Caller, conn: Conn) -> BotView:
    """The connections the bot may use and, for each, the tools: the whole list, replacing what it had."""
    return await store.set_scopes(conn, slug, body)


@router.post("/v1/bots/{slug}/runs", operation_id="runBot", status_code=202)
async def run_bot(slug: str, body: RunIn, request: Request, who: Person) -> RunView:
    """A run of the bot, queued: GET /v1/bot-runs/{id} follows it."""
    state: Any = request.app.state
    return await state.bots.start(who, slug, body.input)


@router.get("/v1/bots/{slug}/runs", operation_id="listBotRuns")
async def list_runs(slug: str, caller: Caller, conn: Conn) -> Runs:
    """Its runs, the newest first (the last 50)."""
    return Runs(runs=await runs.listing(conn, await store.row(conn, slug)))


@router.get("/v1/bot-runs/{run_id}", operation_id="getBotRun")
async def get_run(run_id: uuid.UUID, caller: Caller, conn: Conn) -> RunView:
    return await runs.get(conn, run_id)
