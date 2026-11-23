"""Where every tool call of a bot's agent lands (docs/specs/bot-agent-loop.md, 3 to 5), on Glyphh cloud and from a
rrotor alike. Two things happen to a call, kept apart: whether the bot may make it (`allowed`: its permission mode
and the connection's allow / ask / deny; an action the person must approve stops the run with the question), and the
call itself (`run`): its result, an error the agent is told, or, for `ask_person`, the run stopping with the
agent's own question. What the run used is noted on its row as it goes (`data._steps`, in plain words; what an action
made, for its link cards), with the question it waits on."""

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select, text

from glyphh_server.db import tenancy
from glyphh_server.errors import GlyphhError
from glyphh_server.models import BotRun
from glyphh_server.ops.bots.agent import deciding, permit
from glyphh_server.ops.bots.agent.tools import ASK, DECIDE, Tool
from glyphh_server.ops.bots.agent.turn import ASKED, ERROR, RESULT, Outcome

log = logging.getLogger("glyphh.bots")
STEPS: str = "_steps"
PENDING: str = "_pending"  # an ask_person about a decision's items, waiting on the person: {decision, entries}
STEPS_MAX: int = 200
MADE_MAX: int = 50_000  # an action's result kept for its link cards, when it is this small
NO_TOOL: str = "There is no tool {name}: use only the tools you were given."
BAD_ITEMS: str = "Give a decision's name and its items, each an object (at most {most} at once)."
NO_QUESTION: str = "ask_person takes the question to ask."
TAKE = text(
    "UPDATE bot_runs SET approvals = approvals - :tool WHERE id = :run "
    "AND approvals -> :tool ->> 'digest' = :digest RETURNING id"
)


class Ask(Exception):
    """A tool's own call stops the run to ask the person: its question (the orchestrator's, for a bot it asked)."""

    def __init__(self, question: dict[str, Any]) -> None:
        super().__init__(question.get("question", ""))
        self.question = question


async def _made(tool: Tool, given: dict[str, Any]) -> tuple[bool, Any]:
    """The tool's call: (True, its result) or (False, why it failed, as the agent is told); Ask goes up."""
    assert tool.call is not None
    try:
        return True, await asyncio.wait_for(tool.call(given), tool.seconds)
    except GlyphhError as err:
        return False, err.message
    except (ValueError, PermissionError) as err:  # a host or an input it may not use
        return False, str(err)
    except TimeoutError:
        return False, f"{tool.title} took longer than {tool.seconds:g} seconds"
    except Ask:
        raise
    except Exception as err:  # noqa: BLE001  the agent is told why, as any failed tool call
        return False, f"{tool.title} failed: {err}"


def _items(bot: Any, given: dict[str, Any]) -> tuple[str, list[dict[str, Any]]] | None:
    name, items = given.get("decision"), given.get("items")
    most = deciding.ITEMS_MAX
    fits = isinstance(items, list) and 0 < len(items) <= most and all(isinstance(i, dict) for i in items)
    if name not in (bot.spec.get("gates") or {}) or not fits:
        return None
    assert isinstance(items, list) and isinstance(name, str)
    return name, items


async def _taken(desk: Any, tool: Tool, given: dict[str, Any]) -> bool:
    """The person's yes to this very call, used up; False when the run has none."""
    async with desk.svc.engine.begin() as conn:
        await tenancy.enter(conn, desk.bot.org_id)
        said = {"run": desk.run_id, "tool": tool.key, "digest": permit.digest(given)}
        return (await conn.execute(TAKE, said)).first() is not None


class Desk:
    """One run's tool calls. `svc` is the bots service (its engine, and `go`: a go of the SDK's runner on the bot's
    state); `tools` the bot's, by the name the agent calls each."""

    def __init__(self, svc: Any, bot: Any, run_id: uuid.UUID, loop_run: str, tools: dict[str, Tool]) -> None:
        self.svc, self.bot, self.run_id, self.loop_run, self.tools = svc, bot, run_id, loop_run, tools

    async def _noted(self, change: Callable[[dict[str, Any]], dict[str, Any] | None]) -> dict[str, Any]:
        """The run's data changed in place by `change`, which may answer more of the row's values to set."""
        async with self.svc.engine.begin() as conn:
            await tenancy.enter(conn, self.bot.org_id)
            found = await conn.execute(select(BotRun.data).where(BotRun.id == self.run_id).with_for_update())
            data = dict(found.scalar_one())
            more = change(data) or {}
            await conn.execute(BotRun.__table__.update().where(BotRun.id == self.run_id).values(data=data, **more))
        return data

    async def _step(self, tool: Tool, title: str, ok: bool, made: Any = None) -> None:
        def change(data: dict[str, Any]) -> None:
            steps = [*data.get(STEPS, []), {"tool": tool.key, "title": title, "app": tool.app, "ok": ok}]
            data[STEPS] = steps[-STEPS_MAX:]
            if made is not None and len(str(made)) <= MADE_MAX:
                data[f"{tool.key}-{len(steps)}"] = made

        await self._noted(change)

    async def _asks(self, question: dict[str, Any], pending: dict[str, Any] | None = None) -> Outcome:
        def change(data: dict[str, Any]) -> dict[str, Any]:
            if pending is not None:
                data[PENDING] = pending
            return {"question": question}

        await self._noted(change)
        return Outcome(ASKED, question)

    async def allowed(self, name: str, given: dict[str, Any]) -> Outcome | None:
        """None when the bot may make the call; else the error it is told, or the approval the run stops on."""
        tool = self.tools.get(name)
        if tool is None:
            return Outcome(ERROR, NO_TOOL.format(name=name))
        verdict = permit.verdict(self.bot.permission_mode, tool)
        if verdict == permit.DENY:
            await self._step(tool, tool.title, False)
            log.warning("bot tool refused", extra={"run_id": str(self.run_id), "tool": tool.key, "why": "denied"})
            return Outcome(ERROR, permit.DENIED.format(title=tool.title, app=tool.app))
        if verdict == permit.ASK and not await _taken(self, tool, given):
            return await self._asks(permit.question(tool, given))
        return None

    async def call(self, name: str, given: dict[str, Any]) -> Outcome:
        """A call from a rrotor's agent, or a test's: allowed, then made."""
        return await self.allowed(name, given) or await self.run(name, given)

    async def run(self, name: str, given: dict[str, Any]) -> Outcome:
        """The call made: the tool's result, an error, or the run stopped to ask the person."""
        tool = self.tools[name]
        if tool.key == DECIDE:
            return await self._decide(given)
        if tool.key == ASK:
            return await self._ask(given)
        try:
            ok, got = await _made(tool, given)
        except Ask as ask:
            return await self._asks(ask.question)
        await self._step(tool, tool.title, ok, got if ok and not tool.read_only else None)
        return Outcome(RESULT if ok else ERROR, got)

    async def _decide(self, given: dict[str, Any]) -> Outcome:
        found = _items(self.bot, given)
        if found is None:
            return Outcome(ERROR, BAD_ITEMS.format(most=deciding.ITEMS_MAX))
        name, items = found
        entries = (await self.svc.go(self.bot, lambda r: deciding.judged(r, self.loop_run, name, items))).answer
        await self.settled(name, entries)
        return Outcome(RESULT, deciding.results(entries))

    async def _ask(self, given: dict[str, Any]) -> Outcome:
        said = given.get("question") if isinstance(given.get("question"), str) else ""
        if "decision" not in given and "items" not in given:
            if not said.strip():
                return Outcome(ERROR, NO_QUESTION)
            options = [str(o) for o in given.get("options") or [] if str(o).strip()]
            return await self._asks({"question": said.strip(), "options": options, "approval": False})
        found = _items(self.bot, given)
        if found is None:
            return Outcome(ERROR, BAD_ITEMS.format(most=deciding.ITEMS_MAX))
        name, items = found
        entries = (await self.svc.go(self.bot, lambda r: deciding.judged(r, self.loop_run, name, items))).answer
        question = deciding.question(name, self.bot.spec["gates"][name], entries, said)
        return await self._asks(question, {"decision": name, "entries": entries})

    async def settled(self, name: str, entries: list[dict[str, Any]]) -> None:
        """What was decided of a call's items (by Ada sure of it, the probe, or the person) noted on the run and as a
        step; what Ada was sure of and what the person said kept as the run's decisions."""
        decided = [e for e in entries if e["by"] != "unsure"]
        if not decided:
            return
        made = [e for e in decided if e["by"] in deciding.KEPT]
        if made:
            left = await self.svc.go(self.bot, lambda r: deciding.kept(r, self.loop_run, name, made))
            self.loop_run = left.answer
        results = deciding.results(decided)
        title = f"Decided {name.replace('_', ' ')} for {len(decided)} item{'' if len(decided) == 1 else 's'}"

        def change(data: dict[str, Any]) -> dict[str, Any]:
            data[STEPS] = [*data.get(STEPS, []), {"tool": DECIDE, "title": title, "app": "Ada", "ok": True}]
            had = data.get(name) if isinstance(data.get(name), dict) else {}
            data[name] = {"decisions": [*had.get("decisions", []), *results]}  # the run's answers, by decision
            return {"loop_run": self.loop_run}

        await self._noted(change)


async def answered(desk: Desk, pending: dict[str, Any], answers: dict[int, str]) -> list[dict[str, Any]]:
    """The person answered a decision's items: their answers taught to its Ada model and kept as the run's
    decisions. Answers the entries."""
    name, entries = pending["decision"], pending["entries"]
    got = (await desk.svc.go(desk.bot, lambda r: deciding.answered(r, name, entries, answers))).answer
    await desk.settled(name, got)
    await desk._noted(lambda data: data.pop(PENDING, None) and None)
    return list(got)
