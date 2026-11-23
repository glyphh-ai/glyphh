"""A program run walked (docs/specs/programs.md, 2): on this server, for Glyphh cloud and for a rrotor alike, each go a
background task of the server's own process. A go takes the run from the step it is at, one step after another,
keeping each result as it is made, until the run ends, waits on the person (an ask, an approval, a bot's question)
or waits on its rrotor (a code step). Every step, question and end is a line of the run's audit trail, naming the
bot that did it (ops/programs/events.py)."""

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import func, select

from glyphh_server.db import tenancy
from glyphh_server.models import Bot, Program, ProgramRun
from glyphh_server.ops.bots.runs import machine
from glyphh_server.ops.programs import code, events, flow, runs, steps, store
from glyphh_server.ops.programs.steps import Went

log = logging.getLogger("glyphh.programs")
GONE: str = "Its step {step} is no longer in the program."
NO_BOT: str = "{step}: this program has no bot to do it: choose the program's bot, or name one on the step."


def title_of(step: dict[str, Any]) -> str:
    """A step's name, in plain words."""
    if step.get("title"):
        return str(step["title"])
    said = {"tool": str(step.get("tool", "")).replace("-", " ").replace("_", " "), "ask": step.get("question", "")}
    said |= {"bot": step.get("task", ""), "branch": "Choose the way on", "code": step.get("function", "")}
    return str(said.get(step.get("kind", ""), step.get("id", "")))[:120]


async def rows(engine: Any, org_id: uuid.UUID, run_id: uuid.UUID) -> tuple[Any, Any]:
    """The run and its program."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        run = await runs.row(conn, run_id)
        program = (await conn.execute(select(Program).where(Program.id == run.program_id))).one()
    return run, program


async def bot_of(engine: Any, program: Any, step: dict[str, Any]) -> Any:
    """The bot that does the step: the one it names, else the program's own (None: it has none)."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, program.org_id)
        named = Bot.slug == step["bot"] if step.get("bot") else Bot.id == program.bot_id
        return (await conn.execute(select(Bot).where(named))).one_or_none()


class Walker:
    """The program runs going on this machine. `svc` is the bots service (its engine, Pipedream, its runs)."""

    def __init__(self, svc: Any) -> None:
        self.svc = svc
        self.tasks: dict[asyncio.Task[None], uuid.UUID] = {}

    @property
    def engine(self) -> Any:
        return self.svc.engine

    def spawn(self, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
        task = asyncio.create_task(self._go(org_id, run_id))
        self.tasks[task] = run_id
        task.add_done_callback(lambda t: self.tasks.pop(t, None))

    def stop(self, run_id: uuid.UUID) -> None:
        for task in [t for t, r in self.tasks.items() if r == run_id]:
            task.cancel()

    async def _go(self, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
        began = func.coalesce(ProgramRun.started_at, func.now())
        if not await runs.put(self.engine, org_id, run_id, when="queued", status="running", machine=machine(),
                              started_at=began):  # fmt: skip
            return
        try:
            while await self._step(org_id, run_id):
                pass
        except Exception as err:
            log.exception("program run %s failed", run_id)
            await self.end(org_id, run_id, "failed", f"The run failed: {type(err).__name__}: {err}")

    async def _step(self, org_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """The step the run is at, done and kept: whether the walk goes on."""
        run, program = await rows(self.engine, org_id, run_id)
        if run.status != "running":  # cancelled meanwhile
            return False
        found = {s.get("id"): s for s in store.parsed(program.source)[0]}.get(run.at)
        if found is None:
            await self.end(org_id, run_id, "failed", GONE.format(step=run.at))
            return False
        bot = await bot_of(self.engine, program, found) if found["kind"] in ("tool", "bot", "code") else None
        return await self.kept(program, run, found, bot, await self._did(program, run, found, bot))

    async def _did(self, program: Any, run: Any, step: dict[str, Any], bot: Any) -> Went:
        kind, outputs = step["kind"], dict(run.outputs)
        if kind == "ask":
            return steps.ask(step, outputs)
        if kind == "branch":
            return steps.branch(step, outputs)
        if kind == "code":
            return await code.send(self.svc, program, run, step, bot, outputs)
        if bot is None:
            return Went(error=NO_BOT.format(step=step["id"]))
        if kind == "tool":
            return await steps.tool(self.svc, run, step, bot, outputs)
        return await steps.bot(self.svc, run, step, bot, outputs)

    async def kept(self, program: Any, run: Any, step: dict[str, Any], bot: Any, went: Went) -> bool:
        """What the step came to, on the run and its trail: whether the walk goes on."""
        org_id, outputs = run.org_id, dict(run.outputs)
        if went.child:
            outputs[steps.CHILD] = {**(outputs.get(steps.CHILD) or {}), step["id"]: went.child}
        line = {"title": title_of(step), "bot_id": bot.id if bot is not None else None, "detail": went.detail}
        if went.error:
            await events.note(
                self.engine, org_id, run.id, "step", step["id"], **(line | {"ok": False, "detail": went.error})
            )
            await runs.put(self.engine, org_id, run.id, outputs=outputs, **went.more)
            await self.end(org_id, run.id, "failed", went.error)
            return False
        if went.waits is not None:
            await runs.put(self.engine, org_id, run.id, when="running", status="needs_input", question=went.waits,
                           outputs=outputs, **went.more)  # fmt: skip
            await events.note(
                self.engine, org_id, run.id, "asked", step["id"], **(line | {"title": went.waits["question"]})
            )
            return False
        if went.dispatched:
            await runs.put(self.engine, org_id, run.id, when="running", status="dispatched", **went.more)
            await events.note(self.engine, org_id, run.id, "step", step["id"], **line)
            return False
        outputs[step["id"]] = went.result
        children = {k: v for k, v in (outputs.pop(steps.CHILD, None) or {}).items() if k != step["id"]}
        outputs |= {steps.CHILD: children} if children else {}
        await events.note(self.engine, org_id, run.id, "step", step["id"], **line)
        nxt = flow.after(step, went.result)
        await runs.put(self.engine, org_id, run.id, outputs=outputs, at=nxt or step["id"], **went.more)
        if nxt is None:
            await self.end(org_id, run.id, "done")
            return False
        return True

    async def end(self, org_id: uuid.UUID, run_id: uuid.UUID, status: str, error: str = "", **line: Any) -> bool:
        """The run over, and its trail's last line (`kind`: done, failed, cancelled), only for a run that was still
        live: whether it was."""
        kind = line.pop("kind", status)
        if not await runs.ended(self.engine, org_id, run_id, status, error):
            return False
        await events.note(self.engine, org_id, run_id, kind, ok=status == "done", detail=error, **line)
        return True

    async def wait(self) -> None:
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def close(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
