"""One step of a program run, done (docs/specs/programs.md, 2): what it came to (`Went`). A `tool` step is its bot's
call, as that bot (its connection, its permission mode, the connection's allow / ask / deny: the agent's own rules,
ops/bots/agent/permit.py); a `bot` step is a run of that bot, waited for; an `ask` waits on the person; a `branch`
reads earlier results; a `code` step's function is sent to the program's rrotor (ops/programs/code.py)."""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError
from glyphh_server.ops.bots import orchestrator
from glyphh_server.ops.bots.agent import permit, tools
from glyphh_server.ops.bots.agent.run import fetch
from glyphh_server.ops.programs import flow

CHILD: str = "_child"  # outputs[CHILD][step]: the bot run a bot step waits on
NO_TOOL: str = "{bot} has no tool {tool}: add it to the bot, or pick one it has."
NOT_A_STEP: str = "{tool} is the bot's own way to ask: use an ask step."


@dataclass
class Went:
    result: Any = None
    waits: dict[str, Any] | None = None  # the question the run stops on
    error: str = ""
    detail: str = ""
    dispatched: bool = False  # sent to the rrotor: its result comes back over the link
    child: str = ""  # a bot step's run
    more: dict[str, Any] = field(default_factory=dict)  # changes to the run's row (its approvals)


def _found(own: dict[str, tools.Tool], key: str) -> tools.Tool | None:
    return next((t for t in own.values() if t.key == key or t.name in (key, tools.named(key))), None)


async def tool(svc: Any, run: Any, step: dict[str, Any], bot: Any, outputs: dict[str, Any]) -> Went:
    """The bot's tool, called as the bot, after its permissions say it may."""
    async with svc.engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        own = await tools.of(svc.pd, conn, bot, lambda given: fetch(bot, given))
    found = _found(own, str(step["tool"]))
    if found is None:
        return Went(error=NO_TOOL.format(bot=bot.name, tool=step["tool"]))
    if found.call is None:
        return Went(error=NOT_A_STEP.format(tool=found.name))
    given = flow.render(step.get("input") or {}, outputs)
    given = given if isinstance(given, dict) else {"value": given}
    verdict = permit.verdict(bot.permission_mode, found)
    if verdict == permit.DENY:
        return Went(error=permit.DENIED.format(title=found.title, app=found.app))
    yes = dict(run.approvals)
    if verdict == permit.ASK and yes.pop(step["id"], None) != permit.digest(given):
        return Went(waits={**permit.question(found, given), "kind": "approval", "step": step["id"]})
    try:
        got = await asyncio.wait_for(found.call(given), found.seconds)
    except GlyphhError as err:
        return Went(error=err.message, more={"approvals": yes})
    except TimeoutError:
        return Went(error=f"{found.title} took longer than {found.seconds:g} seconds", more={"approvals": yes})
    except Exception as err:  # noqa: BLE001  the step fails saying why
        return Went(error=f"{found.title} failed: {err}", more={"approvals": yes})
    made = got["ret"] if isinstance(got, dict) and "ret" in got else got  # an app's action: what it returned
    return Went(result=made, detail=found.title, more={"approvals": yes})


async def bot(svc: Any, run: Any, step: dict[str, Any], who: Any, outputs: dict[str, Any]) -> Went:
    """A run of the bot with the step's task (or the one it began, carried on), once it is no longer working."""
    child = (outputs.get(CHILD) or {}).get(step["id"])
    if child is None:
        try:
            made = await svc.queued(who, run.user_id, str(flow.render(step["task"], outputs)))
        except GlyphhError as err:
            return Went(error=f"{who.name} could not start: {err.message}")
        child = str(made.id)
    ran = await orchestrator.settled(svc, who.org_id, uuid.UUID(child))
    while ran.status in orchestrator.WORKING:
        ran = await orchestrator.settled(svc, who.org_id, ran.id)
    if ran.status == "needs_input":
        asks = {**ran.question, "question": f"{who.name} asks: {ran.question.get('question', '')}"}
        return Went(waits={**asks, "kind": "bot", "child_run": child, "step": step["id"]}, child=child)
    if ran.status != "done":
        return Went(error=f"{who.name} could not do it: {ran.error or 'it failed'}", child=child)
    return Went(result=ran.output, detail=f"{who.name} answered", child=child)


def ask(step: dict[str, Any], outputs: dict[str, Any]) -> Went:
    options = [str(o) for o in step.get("options") or [] if str(o).strip()]
    said = str(flow.render(step["question"], outputs))
    return Went(waits={"question": said, "options": options, "approval": False, "kind": "ask", "step": step["id"]})


def branch(step: dict[str, Any], outputs: dict[str, Any]) -> Went:
    got = flow.render(step["on"], outputs)
    return Went(result=got, detail=f"It was {got}" if isinstance(got, str) else "")
