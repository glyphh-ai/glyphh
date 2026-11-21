"""The org's hosted bots (docs/specs/bots.md): each the SDK's bot package (its loop of steps, gates that learn in Ada,
hard limits, its agent's prompt and skills), with a look (its cat), the Claude model its agent steps run on and, per
connection, the tools it may use; run in the background by the SDK's runner. A run that stops for the person waits
(needs_input) until it is answered; a gate's wrong call is corrected and learned. The agent steps run on the org's own
Anthropic key when it has set one (Glyphh's markup charged), else on Glyphh's (Anthropic's rate and the markup), drawn
from the plan's allowance and then the org's balance."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response

from glyphh_server.api.auth import Caller, Cfg, Conn
from glyphh_server.api.templates import Person
from glyphh_server.ops.bots import keys, prices, runs, store, templates
from glyphh_server.ops.bots.prices import BotModels
from glyphh_server.ops.bots.views import (
    AnswerIn,
    BotIn,
    BotPatch,
    Bots,
    BotView,
    Gates,
    KeyIn,
    KeyView,
    RunIn,
    Runs,
    RunView,
    ScopesIn,
    WrongIn,
)

router = APIRouter(tags=["bots"])


def _bots(request: Request) -> Any:
    return request.app.state.bots


@router.get("/v1/bots", operation_id="listBots")
async def list_bots(
    caller: Caller, conn: Conn, q: Annotated[str | None, Query(max_length=200, description="Words it has")] = None
) -> Bots:
    """The org's bots, those whose name or summary has every word of `q` when it is given."""
    return Bots(bots=await store.listing(conn, q))


@router.get("/v1/bots/models", operation_id="listBotModels")
async def list_models(caller: Caller) -> BotModels:
    """The Claude models a bot's agent steps may run on, at their rates."""
    return prices.listing()


@router.get("/v1/bot-templates", operation_id="listBotTemplates")
async def list_templates(
    caller: Caller, q: Annotated[str | None, Query(max_length=200, description="Words its name has")] = None
) -> templates.BotTemplates:
    """The bots marketplace: bot templates Glyphh ships, each ready to copy into the org."""
    return templates.listing(q)


@router.get("/v1/bot-templates/{slug}", operation_id="getBotTemplate")
async def get_template(slug: str, caller: Caller) -> templates.BotTemplate:
    return templates.one(slug)


@router.post("/v1/bot-templates/{slug}/install", operation_id="installBotTemplate", status_code=201)
async def install_template(slug: str, body: templates.InstallIn, who: Caller, conn: Conn, settings: Cfg) -> BotView:
    """The org's own bot copied from the template, scoped to its connection of each app the bot needs (422, reason
    connections, naming the apps to connect first)."""
    return await templates.install(conn, who, settings.secret_key, slug, body)


@router.get("/v1/bot-approvals", operation_id="listBotApprovals")
async def list_approvals(caller: Caller, conn: Conn) -> Runs:
    """The org's approvals queue: every run of its bots waiting on the person (a gate unsure, an approval, a tool its
    connection asks about), oldest first; POST /v1/bot-runs/{id}/answer answers one."""
    return Runs(runs=await runs.waiting(conn))


@router.get("/v1/bot-key", operation_id="getBotKey")
async def get_key(caller: Caller, conn: Conn, settings: Cfg) -> KeyView:
    """Whether the org's bots run on its own Anthropic key (its last four characters), or on Glyphh's."""
    return keys.view(await keys.get(conn), bool(settings.anthropic_api_key))


@router.put("/v1/bot-key", operation_id="setBotKey")
async def set_key(body: KeyIn, request: Request, who: Caller, conn: Conn, settings: Cfg) -> KeyView:
    """The org's own Anthropic API key, tried with Anthropic, then kept sealed: its bots run on it from now on."""
    kept = await keys.put(conn, who, settings.secret_key, body.key, _bots(request).check_key)
    return keys.view(kept, bool(settings.anthropic_api_key))


@router.delete("/v1/bot-key", operation_id="removeBotKey")
async def remove_key(caller: Caller, conn: Conn, settings: Cfg) -> KeyView:
    """The org's own key forgotten: its bots run on Glyphh's, billed by tokens."""
    await keys.remove(conn, caller.org_id)
    return keys.view(None, bool(settings.anthropic_api_key))


@router.post("/v1/bots", operation_id="createBot", status_code=201)
async def create_bot(body: BotIn, caller: Caller, conn: Conn, settings: Cfg) -> BotView:
    """A bot, checked by the SDK (every problem said at once, 422); its slug comes from its name (another bot of the
    org's with that slug: 409 E_CONFLICT)."""
    return await store.create(conn, caller, settings.secret_key, body)


@router.get("/v1/bots/{slug}", operation_id="getBot")
async def get_bot(slug: str, caller: Caller, conn: Conn) -> BotView:
    return await store.one(conn, slug)


@router.patch("/v1/bots/{slug}", operation_id="updateBot")
async def update_bot(slug: str, body: BotPatch, caller: Caller, conn: Conn) -> BotView:
    """What is given changed, the bot checked again; its slug stays."""
    return await store.patch(conn, slug, body)


@router.delete("/v1/bots/{slug}", operation_id="deleteBot", status_code=204)
async def delete_bot(slug: str, caller: Caller, conn: Conn, settings: Cfg) -> Response:
    """The bot deleted, with its runs; its Ada key revoked (its gates' models stay in Ada)."""
    await store.remove(conn, slug, settings.secret_key)
    return Response(status_code=204)


@router.put("/v1/bots/{slug}/connections", operation_id="setBotConnections")
async def set_connections(slug: str, body: ScopesIn, caller: Caller, conn: Conn) -> BotView:
    """The connections the bot may use and, for each, the tools: the whole list, replacing what it had."""
    return await store.set_scopes(conn, slug, body)


@router.get("/v1/bots/{slug}/gates", operation_id="getBotGates")
async def get_gates(slug: str, request: Request, who: Person) -> Gates:
    """What its gates have learned: per gate its precedents, how often it asked, how often it was right."""
    return Gates(gates=await _bots(request).gates(who, slug))


@router.post("/v1/bots/{slug}/runs", operation_id="runBot", status_code=202)
async def run_bot(slug: str, body: RunIn, request: Request, who: Person) -> RunView:
    """A run of the bot, queued: GET /v1/bot-runs/{id} follows it (one live run a bot: 409 while one is)."""
    return await _bots(request).start(who, slug, body.input)


@router.get("/v1/bots/{slug}/runs", operation_id="listBotRuns")
async def list_runs(slug: str, caller: Caller, conn: Conn) -> Runs:
    """Its runs, the newest first (the last 50)."""
    return Runs(runs=await runs.listing(conn, await store.row(conn, slug)))


@router.get("/v1/bot-runs/{run_id}", operation_id="getBotRun")
async def get_run(run_id: uuid.UUID, caller: Caller, conn: Conn) -> RunView:
    return await runs.get(conn, run_id)


@router.post("/v1/bot-runs/{run_id}/answer", operation_id="answerBotRun", status_code=202)
async def answer_run(run_id: uuid.UUID, body: AnswerIn, request: Request, who: Person) -> RunView:
    """The run that waits on the person, answered: it carries on (422 when the answer does not fit the question)."""
    return await _bots(request).answer(who, run_id, body.answer)


@router.post("/v1/bot-runs/{run_id}/wrong", operation_id="correctBotRun")
async def correct_run(run_id: uuid.UUID, body: WrongIn, request: Request, who: Person) -> dict[str, Any]:
    """A gate called the run (or one of its items) wrong: what it should have said, learned as a precedent."""
    return await _bots(request).wrong(who, run_id, body)


@router.post("/v1/bot-runs/{run_id}/cancel", operation_id="cancelBotRun")
async def cancel_run(run_id: uuid.UUID, request: Request, who: Person) -> RunView:
    """The run that waits on the person, ended: it does not carry on."""
    return await _bots(request).cancel(who, run_id)
