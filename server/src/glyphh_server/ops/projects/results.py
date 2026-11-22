"""A project's steps' results, each taken once and moving its run on (docs/specs/bots.md, 10): a rrotor's as it comes
up the link (`landed`: its seq past the last its turn took, from the run's rrotor), Glyphh cloud's as its task ends
(`took`: while its turn is still out). An orchestrator's pick becomes the turn of the bot it named (one it did not
name well is taken as wait your turn takes it), or the run's end when it says the project is done; a bot's turn is
its pull request (waiting for the person, or merged at once with review end) or no change; a merge or a reject, then
the next turn."""

import logging
import uuid
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select, update

from glyphh_server.db import tenancy
from glyphh_server.models import ProjectRun, ProjectTurn
from glyphh_server.models.project import TURN_OUT
from glyphh_server.ops.bots.runs import now
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Ran
from glyphh_server.ops.projects import final, runs, turns
from glyphh_server.ops.projects.steps import Steps

log = logging.getLogger("glyphh.projects")
OLD_RROTOR: str = " (an orchestrator needs rrotor 0.6 or later: update the project's rrotor, or use wait your turn)"
NO_WHY: str = "It is your turn."


class Results(Steps):
    async def landed(self, runtime: Runtime, msg: Ran) -> None:
        """A rrotor's result (a pick, a turn, or its merge or reject), taken once."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, runtime.org_id)
            on_it = ProjectTurn.run_id.in_(select(ProjectRun.id).where(ProjectRun.rrotor_id == runtime.id))
            mine = (ProjectTurn.call_id == msg.run_id, ProjectTurn.status.in_(TURN_OUT), on_it)
            took = update(ProjectTurn).where(*mine, ProjectTurn.remote_seq < msg.seq).values(remote_seq=msg.seq)
            turn = (await conn.execute(took.returning(ProjectTurn))).first()
            if turn is None:  # a replay, another rrotor's, or a turn ended here (a turn out has its run running)
                log.info("project result skipped", extra={"run_id": str(msg.run_id), "seq": msg.seq})
                return
            run = await runs.row(conn, turn.run_id)
        await self._keep(run, turn, msg.result)

    async def took(self, org_id: uuid.UUID, turn_id: uuid.UUID, result: dict[str, Any]) -> None:
        """Glyphh cloud's result for a step, unless its turn ended meanwhile (the run cancelled)."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            out = (ProjectTurn.id == turn_id, ProjectTurn.status.in_(TURN_OUT))
            turn = (await conn.execute(select(ProjectTurn).where(*out))).first()
            if turn is None:
                return
            run = await runs.row(conn, turn.run_id)
        await self._keep(run, turn, result)

    async def _keep(self, run: Any, turn: Any, result: dict[str, Any]) -> None:
        try:
            await self._took(run, turn, result)
        except Exception as err:  # taken: a replay would be skipped, so the run is ended now, saying why
            log.exception("project result not kept", extra={"run_id": str(run.id)})
            await self.end(run.org_id, run.id, "failed", f"The step's result could not be kept: {err}")

    async def _took(self, run: Any, turn: Any, result: dict[str, Any]) -> None:
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        if result.get("status") != "done":
            said = (
                f"{turn.bot_name}'s turn {turn.n} {result.get('status')}: {data.get('reason') or result.get('status')}"
            )
            old = turn.status == "picking" and not run.on_cloud
            await self.end(run.org_id, run.id, "failed", said + (OLD_RROTOR if old else ""))
            return
        await self.used(run, turn, data.get("usage"))
        if turn.status == "picking":
            await self._picked(run, turn, data)
        elif turn.status == "running":
            await self._turned(run, turn, data)
        else:
            status = "rejected" if turn.status == "rejecting" else str(data.get("status") or "merged")
            error = str(data.get("reason") or "") if status == "conflict" else ""
            await self.put_turn(run.org_id, turn.id, status=status, error=error, finished_at=now())
            await self.next(run.org_id, run.id)

    async def _picked(self, run: Any, turn: Any, data: dict[str, Any]) -> None:
        if (found := await self.standing(run.org_id, run.id)) is None:
            return
        _, taken, crew = found
        before = [t for t in taken if t.id != turn.id]
        named, why, done = turns.picked(str(data.get("answer") or ""), [b.slug for b in crew])
        if done:
            said = why if run.on_cloud else ""
            await self.put_turn(run.org_id, turn.id, status="unchanged", done=True, said=said, finished_at=now())
            await final.finish(self, run, before, "orchestrator")
            return
        if named is None:
            bot, why = self.waiting(before, crew, turns.idle_row(runs.went(before))), ""
        else:
            bot, why = next(b for b in crew if b.slug == named), why or NO_WHY
        await self.turn(run, before, crew, bot, picking=turn, why=why)

    async def _turned(self, run: Any, turn: Any, data: dict[str, Any]) -> None:
        opened = data.get("status") == "open"
        said = str(data.get("said") or "")
        kept = {k: data.get(k) for k in ("pr_url", "number", "head_sha")}
        kept |= {"files": data.get("files") or [], "said": said, "title": str(data.get("title") or "")}
        kept |= {"done": turns.is_done(said), "status": "open" if opened else "unchanged"}
        await self.put_turn(run.org_id, turn.id, **kept, finished_at=None if opened else now())
        if not opened:
            await self.next(run.org_id, run.id)
        elif run.review == "end":
            await self.review(run, SimpleNamespace(**turn._asdict() | kept), "merge")
        else:
            await self.put_run(run.org_id, run.id, status="needs_input")

    async def review(self, run: Any, turn: Any, answer: str) -> None:
        """The turn's pull request merged or closed: by the run's rrotor (a call, its result moves the run on), or
        for a run on Glyphh cloud here, through GitHub's API."""
        if run.on_cloud:
            await final.settle(self, run, turn, answer)
            await self.put_run(run.org_id, run.id, status="running")
            await self.next(run.org_id, run.id)
            return
        call_id = uuid.uuid4()
        status = "merging" if answer == "merge" else "rejecting"
        await self.put_run(run.org_id, run.id, status="running")
        await self.put_turn(run.org_id, turn.id, status=status, call_id=call_id)
        await self.send(run, call_id, answer, {"pr_url": turn.pr_url})
