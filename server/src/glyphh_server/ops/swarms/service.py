"""The org's swarms' runs (app.state.bots.swarms): started on a task (the swarm's rrotor linked now and the org's
GitHub token saved, else refused), each turn's result taken as it comes back over the link (once: its seq past the
last its turn took, from the run's rrotor), a pull request that waits answered (merge or reject, each a call of its
own), and a run cancelled (its turn out on the rrotor stopped; an open pull request stays open on GitHub)."""

import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, Invalid
from glyphh_server.models import SwarmRun, SwarmTurn
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Ran
from glyphh_server.ops.swarms import github, runs, store, turns
from glyphh_server.ops.swarms.engine import OUT, Engine, now, now_stamp
from glyphh_server.ops.swarms.views import SwarmRunView

log = logging.getLogger("glyphh.swarms")
LIVE: str = "The swarm has a run going: answer its pull request, or cancel it, first."
NOT_WAITING: str = "That swarm run is not waiting on a pull request."
CANCELLED: str = "cancelled"


class Swarms(Engine):
    def __init__(self, engine: AsyncEngine, settings: Settings, hub: Hub, http: httpx.AsyncClient) -> None:
        super().__init__(engine, settings, hub)
        self.check_github: github.Check = github.checker(http)  # a token tried with GitHub (a test sets a fake)

    async def get(self, org_id: uuid.UUID, run_id: uuid.UUID) -> SwarmRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return await runs.get(conn, run_id)

    async def start(self, who: Principal, slug: str, task: str) -> SwarmRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            swarm = await store.row(conn, slug)
            await calls.linked(conn, swarm.runs_on)
            await github.token(conn, self.secret)
            crew = [str(b.id) for b in await store.crew(conn, swarm.members)]
        if not crew:
            raise Invalid("The swarm's crew has no bot left: add one.", reason="members")
        values = {"org_id": who.org_id, "swarm_id": swarm.id, "user_id": who.user_id, "task": task, "members": crew}
        values |= {"rounds": swarm.rounds, "review": swarm.review, "rrotor_id": swarm.runs_on, "stamp": now_stamp()}
        try:
            async with self.engine.begin() as conn:
                await tenancy.enter(conn, who.org_id)
                made = SwarmRun.__table__.insert().values(**values).returning(SwarmRun.id)
                run_id = (await conn.execute(made)).scalar_one()
        except IntegrityError as err:
            raise Conflict(LIVE, slug=slug) from err
        await self.next(who.org_id, run_id)
        return await self.get(who.org_id, run_id)

    async def landed(self, runtime: Runtime, msg: Ran) -> None:
        """A turn's result (its turn, or its merge or reject), taken once and moving its run on."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, runtime.org_id)
            on_it = SwarmTurn.run_id.in_(select(SwarmRun.id).where(SwarmRun.rrotor_id == runtime.id))
            mine = (SwarmTurn.call_id == msg.run_id, SwarmTurn.status.in_(OUT), SwarmTurn.remote_seq < msg.seq, on_it)
            took = update(SwarmTurn).where(*mine).values(remote_seq=msg.seq).returning(SwarmTurn)
            turn = (await conn.execute(took)).first()
            if turn is None:  # a replay, another rrotor's, or a turn ended here (a turn out has its run running)
                log.info("swarm result skipped", extra={"run_id": str(msg.run_id), "seq": msg.seq})
                return
            run = await runs.row(conn, turn.run_id)
        try:
            await self._took(run, turn, msg.result)
        except Exception as err:  # taken: a replay would be skipped, so the run is ended now, saying why
            log.exception("swarm result not kept", extra={"run_id": str(run.id)})
            await self.end(run.org_id, run.id, "failed", f"The rrotor's result could not be kept: {err}")

    async def _took(self, run: Any, turn: Any, result: dict[str, Any]) -> None:
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        if result.get("status") != "done":
            said = data.get("reason") or result.get("status")
            await self.end(
                run.org_id, run.id, "failed", f"{turn.bot_name}'s turn {turn.n} {result.get('status')}: {said}"
            )
            return
        if turn.status == "running":
            await self._turned(run, turn, data)
            return
        status = "rejected" if turn.status == "rejecting" else str(data.get("status") or "merged")
        error = str(data.get("reason") or "") if status == "conflict" else ""
        await self.put_turn(run.org_id, turn.id, status=status, error=error, finished_at=now())
        await self.after(run, turn)

    async def _turned(self, run: Any, turn: Any, data: dict[str, Any]) -> None:
        opened = data.get("status") == "open"
        said = str(data.get("said") or "")
        kept = {k: data.get(k) for k in ("pr_url", "number", "head_sha")}
        kept |= {"files": data.get("files") or [], "said": said, "title": str(data.get("title") or "")}
        kept |= {"done": turns.is_done(said), "status": "open" if opened else "unchanged"}
        await self.put_turn(run.org_id, turn.id, **kept, finished_at=None if opened else now())
        if not opened:
            await self.after(run, turn)
        elif run.review == "auto":
            await self.review(run, turn, "merge")
        else:
            await self.put_run(run.org_id, run.id, status="needs_input")

    async def after(self, run: Any, turn: Any) -> None:
        """Glyphh Bot's DONE rule, then the next bot's turn: a bot that said DONE is kept, any other answer empties
        the row; two in a row (or a crew of one's one) ends the swarm."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, run.org_id)
            said = (await conn.execute(select(SwarmTurn.said).where(SwarmTurn.id == turn.id))).scalar_one()
        done = [*run.done, turn.bot_slug] if turns.is_done(said) else []
        await self.put_run(run.org_id, run.id, done=done)
        if turns.crew_done(done, len(run.members)):
            await self.end(run.org_id, run.id, "done")
        else:
            await self.next(run.org_id, run.id)

    async def review(self, run: Any, turn: Any, answer: str) -> None:
        call_id = uuid.uuid4()
        status = "merging" if answer == "merge" else "rejecting"
        await self.put_turn(run.org_id, turn.id, status=status, call_id=call_id)
        await self.put_run(run.org_id, run.id, status="running")
        await self.send(run.org_id, run, call_id, answer, {"pr_url": turn.pr_url})

    async def answer(self, who: Principal, run_id: uuid.UUID, answer: str) -> SwarmRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            run = await runs.row(conn, run_id)
            turn = await runs.open_turn(conn, run_id)
        if run.status != "needs_input" or turn is None:
            raise Conflict(NOT_WAITING, run_id=str(run_id))
        await self.review(run, turn, answer)
        return await self.get(who.org_id, run_id)

    async def cancel(self, who: Principal, run_id: uuid.UUID) -> SwarmRunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            run = await runs.row(conn, run_id)
            out = [t for t in await runs.turns(conn, run_id) if t.status in OUT]
        if run.status not in ("running", "needs_input"):
            raise Conflict("That swarm run has ended.", run_id=str(run_id))
        for t in out:
            await calls.cancel(self.hub, run.rrotor_id, t.call_id)
        await self.end(who.org_id, run_id, "failed", CANCELLED, turn="cancelled")
        return await self.get(who.org_id, run_id)
