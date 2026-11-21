"""The bots on this machine (app.state.bots): their runs, each the SDK's runner in a worker thread (ops/bots/engine.py)
started by a background task of the server's own process, a few at once (bot_runs_at_once; the rest wait their turn,
queued). Started, a run is committed queued before its task begins, so its page finds it at once; answered, a run
that waited on the person is queued again and carries on. The agent steps run on the org's own Anthropic key when it
has set one (nothing charged), else on Glyphh's (billed by tokens through the meter); with neither, a run is refused.
At the server's start, the runs this machine was running when it stopped are failed."""

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from glyphh.bots import BotError, Runner
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, GlyphhError, Unavailable
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import engine, keys, mend, runs, store
from glyphh_server.ops.bots.goes import NO_KEY, Goes
from glyphh_server.ops.bots.views import RunView, WrongIn

log = logging.getLogger("glyphh.bots")


class Bots(Goes):
    def __init__(self, engine_: AsyncEngine, redis: Redis, settings: Settings, http: httpx.AsyncClient):
        super().__init__(engine_, redis, settings, http)
        self.gate = asyncio.Semaphore(settings.bot_runs_at_once)
        self.tasks: set[asyncio.Task[None]] = set()

    async def recover(self) -> int:
        """At the server's start; without the database, the server starts anyway (health says it is degraded)."""
        try:
            cut = await runs.recover(self.engine, runs.machine())
        except Exception:
            log.exception("could not fail the bot runs cut off by a restart")
            return 0
        if cut:
            log.warning("failed %d bot runs cut off by a restart", cut)
        return cut

    def _spawn(self, work: Any) -> None:
        task = asyncio.create_task(work)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def start(self, who: Principal, slug: str, given: str) -> RunView:
        """A run of the bot, queued: it starts when one of this machine's places is free."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            bot = await store.row(conn, slug)
            has_own = await keys.get(conn) is not None
        if not has_own and not self.settings.anthropic_api_key:
            raise Unavailable(NO_KEY, reason="anthropic_off")
        made = await runs.create(self.engine, who.org_id, bot, who.user_id, given)
        self._spawn(self._run(bot.org_id, bot.id, made.id, lambda r: r.run(given=given or None)))
        return made

    async def answer(self, who: Principal, run_id: uuid.UUID, answer: Any) -> RunView:
        """A run that waits on the person, carried on with their answer (refused when it does not fit)."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            found = await runs.row(conn, run_id)
        if found.status != "needs_input":
            raise Conflict(mend.NOT_WAITING, run_id=str(run_id))
        answer = mend.fits(found.question, answer)
        if not await runs.queue(self.engine, who.org_id, run_id):
            raise Conflict(mend.NOT_WAITING, run_id=str(run_id))
        self._spawn(self._run(found.org_id, found.bot_id, run_id, lambda r: r.resume(answer)))
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            return await runs.get(conn, run_id)

    async def _run(self, org_id: uuid.UUID, bot_id: uuid.UUID, run_id: uuid.UUID, act: Callable[[Runner], Any]) -> None:
        async with self.gate:
            try:
                bot = await self.bot(org_id, bot_id)
                claude, own = await self.claude_of(bot)
                await runs.start(self.engine, org_id, run_id, own)
                left = await self.go(bot, act, claude)
                assert left.result is not None
                async with self.engine.begin() as conn:
                    await tenancy.enter(conn, org_id)
                    run = await runs.row(conn, run_id)
                out = engine.output(bot, left.result)
                await runs.ended(self.engine, run, left.result, out, left.tokens, left.charged)
            except (BotError, GlyphhError) as err:
                await runs.failed(self.engine, org_id, run_id, err.message)
            except Exception as err:
                log.exception("bot run %s failed", run_id)
                await runs.failed(self.engine, org_id, run_id, f"The run failed: {type(err).__name__}: {err}")

    async def wrong(self, who: Principal, run_id: uuid.UUID, body: WrongIn) -> dict[str, Any]:
        """A gate decided the run (or one item of it) wrong: what it should have said, learned as a precedent."""
        return await mend.wrong(self, who, run_id, body)

    async def cancel(self, who: Principal, run_id: uuid.UUID) -> RunView:
        """A run that waits on the person, ended: it does not carry on."""
        return await mend.cancel(self, who, run_id)

    async def gates(self, who: Principal, slug: str) -> dict[str, Any]:
        """What the bot's gates have learned: per gate its precedents, how often it asked and was right."""
        return await mend.gates(self, who, slug)

    async def wait(self) -> None:
        """Every run started here, finished (the tests')."""
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def close(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
