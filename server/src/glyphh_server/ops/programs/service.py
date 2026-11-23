"""The programs on this server (app.state.bots.programs; docs/specs/programs.md): a run started (by a person, the
schedule or the connector), refused while the program cannot run; a waiting run answered (an ask's answer is its
step's result, a yes to an action lets that very call run once, a bot's question goes to that bot's run); cancelled;
a code step's result back from the rrotor; a bot run that ended where the person answered it, waking the program run
that waited on it; and at the server's start, the runs it was walking failed."""

import logging
import uuid
from typing import Any

from sqlalchemy import select, update

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, Invalid
from glyphh_server.models import ProgramRun
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import mend
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Ran
from glyphh_server.ops.programs import code, events, flow, runs, store
from glyphh_server.ops.programs.views import ProgramRunView
from glyphh_server.ops.programs.walk import Walker, bot_of, rows, title_of

log = logging.getLogger("glyphh.programs")
CANNOT: str = "{name} cannot run yet: {problems}"
EMPTY: str = "{name} has no steps yet."
NOT_WAITING: str = "That run is not waiting on an answer."
SAID_NO: str = "Stopped: the person said no to {question}"


class Programs(Walker):
    async def start(self, who: Principal, slug: str, given: str, trigger: str = "person") -> ProgramRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            program = await store.row(conn, slug)
        return await self.queued(program, who.user_id, given, trigger)

    async def queued(self, program: Any, user_id: Any, given: str, trigger: str) -> ProgramRunView:
        """A run of the program, queued here: refused while its steps cannot run (each problem said) or its last
        run is live."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, program.org_id)
            shown = await store.view(conn, program)
        if shown.problems:
            raise Invalid(CANNOT.format(name=program.name, problems="; ".join(shown.problems)), reason="program",
                          problems=shown.problems)  # fmt: skip
        if not shown.flow:
            raise Invalid(EMPTY.format(name=program.name), reason="program")
        made = await runs.create(self.engine, program, user_id, trigger, given, shown.flow[0]["id"])
        await runs.put(self.engine, program.org_id, made.id, outputs={"input": given})
        await events.note(self.engine, program.org_id, made.id, "started", user_id=user_id, detail=trigger)
        self.spawn(program.org_id, made.id)
        return await runs.shown(self.engine, program.org_id, made.id)

    async def answer(self, who: Principal, run_id: uuid.UUID, answer: Any) -> ProgramRunView:
        run, program = await rows(self.engine, who.org_id, run_id)
        asked = dict(run.question)
        if run.status != "needs_input":
            raise Conflict(NOT_WAITING, run_id=str(run_id))
        if asked.get("kind") == "bot":  # the bot's own run takes it; the program carries on when it ends
            await self.svc.answer(who, uuid.UUID(asked["child_run"]), answer)
            return await self._again(who, run, answer, {})
        said = mend.fits(asked, answer)
        if asked.get("kind") == "approval":
            if said != "yes":
                return await self._no(who, run, asked)
            return await self._again(who, run, said, {"approvals": {**run.approvals, run.at: asked["digest"]}})
        return await self._answered(who, run, program, said)

    async def _again(self, who: Principal, run: Any, said: Any, more: dict[str, Any]) -> ProgramRunView:
        if not await runs.put(
            self.engine, who.org_id, run.id, when="needs_input", status="queued", question={}, **more
        ):
            raise Conflict(NOT_WAITING, run_id=str(run.id))
        await events.note(self.engine, who.org_id, run.id, "answered", run.at, user_id=who.user_id, detail=str(said))
        self.spawn(who.org_id, run.id)
        return await runs.shown(self.engine, who.org_id, run.id)

    async def _no(self, who: Principal, run: Any, asked: dict[str, Any]) -> ProgramRunView:
        await events.note(self.engine, who.org_id, run.id, "answered", run.at, user_id=who.user_id, detail="no")
        await self.end(who.org_id, run.id, "failed", SAID_NO.format(question=asked["question"]))
        return await runs.shown(self.engine, who.org_id, run.id)

    async def _answered(self, who: Principal, run: Any, program: Any, said: Any) -> ProgramRunView:
        """An ask's answer: its step's result, and the walk on from there."""
        step = {s.get("id"): s for s in store.parsed(program.source)[0]}.get(run.at) or {"id": run.at}
        nxt = flow.after(step, said)
        outputs = {**run.outputs, run.at: said}
        if nxt is None:
            await runs.put(self.engine, who.org_id, run.id, outputs=outputs)
            await events.note(self.engine, who.org_id, run.id, "answered", run.at, user_id=who.user_id, detail=said)
            await self.end(who.org_id, run.id, "done", title=title_of(step))
            return await runs.shown(self.engine, who.org_id, run.id)
        return await self._again(who, run, said, {"outputs": outputs, "at": nxt})

    async def cancel(self, who: Principal, run_id: uuid.UUID) -> ProgramRunView:
        run, program = await rows(self.engine, who.org_id, run_id)
        self.stop(run_id)
        if not await self.end(who.org_id, run_id, "failed", "cancelled", kind="cancelled", user_id=who.user_id):
            raise Conflict("That run is over already.", run_id=str(run_id))
        if run.status == "dispatched" and program.runs_on is not None:
            await calls.cancel(self.svc.remote.hub, program.runs_on, run_id)
        return await runs.shown(self.engine, who.org_id, run_id)

    async def landed(self, runtime: Runtime, msg: Ran) -> bool:
        """A code step's result over the rrotor's link: kept, and the walk on (False: no program run has its id)."""
        run = await code.taken(self.engine, runtime, msg)
        if run is None:
            async with self.engine.begin() as conn:
                await tenancy.enter(conn, runtime.org_id)
                known = (await conn.execute(select(ProgramRun.id).where(ProgramRun.id == msg.run_id))).first()
            return known is not None
        _, program = await rows(self.engine, run.org_id, run.id)
        step = {s.get("id"): s for s in store.parsed(program.source)[0]}.get(run.at) or {"id": run.at, "kind": "code"}
        if await self.kept(program, run, step, await bot_of(self.engine, program, step), code.came(msg.result)):
            await runs.put(self.engine, run.org_id, run.id, when="running", status="queued")
            self.spawn(run.org_id, run.id)
        return True

    async def woken(self, org_id: uuid.UUID, bot_run_id: uuid.UUID) -> None:
        """A bot run ended that a program run waits on (its question answered at the bot's own run): it walks on."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            waiting = ProgramRun.question["child_run"].astext == str(bot_run_id)
            woke = update(ProgramRun).where(ProgramRun.status == "needs_input", waiting)
            found = (await conn.execute(woke.values(status="queued", question={}).returning(ProgramRun.id))).all()
        for (run_id,) in found:  # each taken once, by the statement
            self.spawn(org_id, run_id)

    async def recover(self) -> int:
        cut = await runs.recover(self.engine)
        for run_id, org_id in cut:
            await events.note(self.engine, org_id, run_id, "failed", ok=False, detail=runs.CUT)
        return len(cut)
