"""The bots on this machine (app.state.bots): their runs, each one Claude Agent SDK turn (ops/bots/agent; docs/specs/
bot-agent-loop.md) started by a background task of the server's own process, a few at once (ops/bots/agent/tasks.py).
Started, a run is committed queued before its task begins, so its page finds it at once; answered, a run that waited
on the person is queued again and its session carried on. A run is billed on the org's own Anthropic key when it has
set one, else on Glyphh's, by tokens through the meter on either (ops/bots/prices.py); with neither, a run is
refused. A bot set to run on one of the org's rrotors runs there (ops/bots/remote.py), its results back over the
link (`landed`, a project's steps' too: ops/projects/service.py, held here as `projects`). At the server's start,
the runs this machine was running when it stopped are failed."""

import logging
import uuid
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import mend, remote_out, runs, store
from glyphh_server.ops.bots.agent import run as agent_run
from glyphh_server.ops.bots.agent import session
from glyphh_server.ops.bots.agent.tasks import Carried, Tasks
from glyphh_server.ops.bots.remote import Remote
from glyphh_server.ops.bots.views import RunView, WrongIn
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Ran
from glyphh_server.ops.programs.service import Programs
from glyphh_server.ops.projects.service import Projects

log = logging.getLogger("glyphh.bots")
CANCELLED: str = "cancelled"
TOO_MANY: str = "It has reached the most runs it may make in a day ({most})."


class Bots(Tasks):
    def __init__(self, engine_: AsyncEngine, redis: Redis, settings: Settings, http: httpx.AsyncClient, hub: Hub):
        super().__init__(engine_, redis, settings, http)
        self.remote = Remote(self, hub)
        self.projects = Projects(self, hub, http)
        self.programs = Programs(self)

    async def recover(self) -> int:
        """At the server's start; without the database, the server starts anyway (health says it is degraded)."""
        try:
            cut = await runs.recover(self.engine, runs.machine())
            cut += await self.projects.recover(runs.machine())
            cut += await self.programs.recover()
        except Exception:
            log.exception("could not fail the bot runs cut off by a restart")
            return 0
        if cut:
            log.warning("failed %d bot runs cut off by a restart", cut)
        return cut

    async def start(self, who: Principal, slug: str, given: str) -> RunView:
        """A run of the bot, queued: it starts when one of this machine's places is free (or on its rrotor)."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            bot = await store.row(conn, slug)
        return await self.queued(bot, who.user_id, given)

    async def queued(self, bot: Any, user_id: uuid.UUID | None, given: str) -> RunView:
        """A run of the bot (the person's, its schedule's: ops/bots/due.py, or the orchestrator's), queued here, or
        sent to the rrotor it runs on. Past its runs a day, the run is made and skipped, saying so."""
        most = agent_run.limits(bot)["runs_per_day"]
        over = await runs.today(self.engine, bot) >= most
        if over:
            made = await runs.create(self.engine, bot.org_id, bot, user_id, given)
            await runs.skipped(self.engine, bot.org_id, made.id, TOO_MANY.format(most=most))
            return await self.shown(bot.org_id, made.id)
        if bot.runs_on is not None:
            return await self.remote.start(bot, user_id, given)
        await self.key_of(bot)
        made = await runs.create(self.engine, bot.org_id, bot, user_id, given)
        self.spawn((bot.org_id, bot.id), made.id, user_id, given, None)
        return made

    async def shown(self, org_id: uuid.UUID, run_id: uuid.UUID) -> RunView:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return await runs.get(conn, run_id)

    async def _waiting(self, who: Principal, run_id: uuid.UUID) -> Any:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            return await runs.row(conn, run_id)

    async def answer(self, who: Principal, run_id: uuid.UUID, answer: Any) -> RunView:
        """A run that waits on the person, carried on with their answer (refused when it does not fit)."""
        found = await self._waiting(who, run_id)
        if found.status != "needs_input":
            raise Conflict(mend.NOT_WAITING, run_id=str(run_id))
        answer = mend.fits(found.question, answer)
        if found.rrotor_id is not None:
            return await self.remote.answer(who, found, answer)
        if not await runs.queue(self.engine, who.org_id, run_id):
            raise Conflict(mend.NOT_WAITING, run_id=str(run_id))
        carried: Carried = (dict(found.question), answer, who.user_id)
        self.spawn((found.org_id, found.bot_id), run_id, found.user_id, "", carried)
        return await self.shown(who.org_id, run_id)

    async def landed(self, runtime: Runtime, msg: Ran) -> None:
        """A result over a rrotor's link: a bot run's, a program run's code step's, else a project's step's."""
        if not await remote_out.landed(self.remote, runtime, msg) and not await self.programs.landed(runtime, msg):
            await self.projects.landed(runtime, msg)

    async def wrong(self, who: Principal, run_id: uuid.UUID, body: WrongIn) -> dict[str, Any]:
        """A decision of the run (on one item of it) was wrong: what it should have said, learned as a precedent."""
        return await mend.wrong(self, who, run_id, body)

    async def cancel(self, who: Principal, run_id: uuid.UUID) -> RunView:
        """A run ended by the person: one that waits does not carry on, one going here is stopped, one out on its
        rrotor is stopped there."""
        found = await self._waiting(who, run_id)
        if found.rrotor_id is not None and found.status == "dispatched":
            return await self.remote.cancel(who, found)
        if found.status in ("queued", "running"):
            self.stop(run_id)
            await runs.failed(self.engine, who.org_id, run_id, CANCELLED)
            shown = await self.shown(who.org_id, run_id)
        else:
            shown = await mend.cancel(self, who, run_id)
        await session.drop(self.engine, who.org_id, run_id)
        if found.rrotor_id is not None:
            await self.remote.drop(found)
        return shown

    async def _woken(self, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """A run over: what waited on it (a run of the orchestrator, a program's run) carries on."""
        await super()._woken(org_id, run_id)
        await self.programs.woken(org_id, run_id)

    async def gates(self, who: Principal, slug: str) -> dict[str, Any]:
        """What the bot's decisions have learned: per decision its precedents, how often it asked and was right."""
        return await mend.gates(self, who, slug)

    async def wait(self) -> None:
        """Every run started here, finished (the tests')."""
        while self.tasks or self.programs.tasks:  # a program's bot step starts a bot run, and its end wakes a program
            await super().wait()
            await self.programs.wait()
        await self.projects.wait()

    async def close(self) -> None:
        await super().close()
        await self.projects.close()
        await self.programs.close()
