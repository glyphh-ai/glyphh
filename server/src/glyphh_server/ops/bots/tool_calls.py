"""A tool's call from a bot running on a rrotor (glyphh_bot's agent: POST /v1/bots/runs/{id}/tool, bearer the run's
tool token, `{tool, input}`; docs/specs/bot-agent-loop.md, 6.2), answered `{result}`, `{error}` (the agent is told)
or `{ask: true, question}`: the run has stopped to ask the person, and the rrotor ends the turn. It lands at the
same desk a run on Glyphh cloud uses (ops/bots/agent/desk.py), so the bot's permissions and Ada's decisions are held
here, not on the machine: a rrotor taken over holds the run's token and still cannot run a tool the person was to be
asked about. The token opens this run only, while it is out on its rrotor.

Two calls are the machine's own, asked before it acts: `file_change`, a write or a move in the bot's folders
(ops/bots/files.py), and `run_script`, one of the scripts a plugin of the bot declares (7.4). Each is `{result:
{allowed: true}}` at once when the bot does not ask first; under Ask me first a file's change is allowed only by
taking the person's yes to that very change (`{allowed: false}`: the rrotor asks), and a script asks here. Nothing
of a file comes here."""

import logging
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from glyphh_server.db import tenancy
from glyphh_server.models import Bot
from glyphh_server.ops.bots import approvals, files, orchestrator, remote_in, runs
from glyphh_server.ops.bots.agent import run as agent_run
from glyphh_server.ops.bots.agent.tools import Tool
from glyphh_server.ops.bots.agent.turn import ASKED, ERROR
from glyphh_server.ops.bots.goes import Goes

log = logging.getLogger("glyphh.bots")
NOT_OUT: str = "This run is not out on its rrotor now."
SCRIPT: str = "run_script"
NO_SCRIPT: str = "run_script takes {plugin, script}: a script one of the bot's plugins declares."
ANY: dict[str, Any] = {"type": "object", "properties": {}}


class ToolIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool: str = Field(min_length=1, max_length=200, description="One of the bot's tools, by the name it was given")
    input: Any = Field(None, description="The call's input")


async def _out(svc: Goes, org_id: uuid.UUID, run_id: uuid.UUID) -> tuple[Any, Any]:
    """The run and its bot, while the run is out on its rrotor; else (None, None)."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        run = await runs.row(conn, run_id)
        if run.status != "dispatched" or run.rrotor_id is None:
            return None, None
        return run, (await conn.execute(select(Bot).where(Bot.id == run.bot_id))).one()


async def call(svc: Goes, token: str, run_id: uuid.UUID, body: ToolIn) -> dict[str, Any]:
    """The tool's answer; a refusal is logged."""
    org_id = remote_in.opened(svc.settings.secret_key, token, run_id)
    run, bot = await _out(svc, org_id, run_id)
    if run is None:
        said: dict[str, Any] = {"error": NOT_OUT}
    elif body.tool == files.TOOL:
        said = await _file(svc, bot, run_id, body.input)
    else:
        said = await _answer(svc, bot, run, body)
    if "error" in said:
        log.warning("bot tool call refused", extra={"run_id": str(run_id), "tool": body.tool, "why": said["error"]})
    return said


async def _file(svc: Goes, bot: Any, run_id: uuid.UUID, given: Any) -> dict[str, Any]:
    """Whether the run may make this change to a file now: at once unless its bot asks first, and then only by
    taking the person's yes to it (used once); never outside the folders the bot may change."""
    asked = files.change(given)
    if asked is None:
        return {"error": files.BAD}
    outside = files.may_change(bot.folders, asked)
    if outside is not None:
        return {"error": files.NO_FOLDERS.format(path=outside, name=bot.name)}
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        allowed = bot.permission_mode != "ask" or await approvals.take_file(conn, run_id, asked)
    return {"result": {"allowed": allowed}}


def _script(given: dict[str, Any]) -> Tool:
    """A plugin's script as a tool of the bot's, for the desk: an action of no app, allowed once it may run."""

    async def allowed(_: dict[str, Any]) -> Any:
        return {"allowed": True}

    title = f"Run {str(given.get('script', '')).rsplit('/', 1)[-1]}"
    return Tool(SCRIPT, SCRIPT, title, "", ANY, False, call=allowed)


async def _answer(svc: Goes, bot: Any, run: Any, body: ToolIn) -> dict[str, Any]:
    given = body.input if isinstance(body.input, dict) else {}
    more = orchestrator.tools(svc, bot, run.user_id)
    _, desk, found = await agent_run.prepared(svc, bot, run.id, more)
    if body.tool == SCRIPT:
        declared = {(p.name, s) for p in found for s in p.scripts}
        if (given.get("plugin"), given.get("script")) not in declared:
            return {"error": NO_SCRIPT}
        desk.tools[SCRIPT] = _script(given)
        given = {"plugin": given["plugin"], "script": given["script"], "args": given.get("args")}
    got = await desk.call(body.tool, given)
    if got.kind == ASKED:
        return {"ask": True, "question": got.value.get("question", "")}
    return {"error": str(got.value)} if got.kind == ERROR else {"result": got.value}
