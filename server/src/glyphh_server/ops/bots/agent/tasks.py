"""The runs going on this machine (docs/specs/bot-agent-loop.md, 2.1, 6.1): each go of a run is a background task of
the server's own process, a few at once (bot_runs_at_once; the rest wait their turn, queued). A go is the person's
message, or, for a run that waited, what they answered (ops/bots/agent/carry.py). A go that fails outside its turn
fails the run saying why, and its session goes with it; when a run is over, a run of the orchestrator that waited on
it is carried on. A task that is cancelled writes nothing: the one who cancelled says so on the run (the person:
ops/bots/service.py), and a run cut off by the server stopping is failed when it starts again (ops/bots/runs.py)."""

import asyncio
import logging
import uuid
from typing import Any

import httpx
from glyphh.bots import BotError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.errors import GlyphhError
from glyphh_server.ops.bots import orchestrator, runs
from glyphh_server.ops.bots.agent import carry, prompt, session
from glyphh_server.ops.bots.agent import run as agent_run
from glyphh_server.ops.bots.agent.desk import Ask
from glyphh_server.ops.bots.goes import Goes

log = logging.getLogger("glyphh.bots")
Carried = tuple[dict[str, Any], Any, uuid.UUID | None]  # the question a run waited on, the answer, who answered


class Tasks(Goes):
    def __init__(self, engine_: AsyncEngine, redis: Redis, settings: Settings, http: httpx.AsyncClient) -> None:
        super().__init__(engine_, redis, settings, http)
        self.gate = asyncio.Semaphore(settings.bot_runs_at_once)
        self.tasks: dict[asyncio.Task[None], uuid.UUID] = {}

    def spawn(
        self, bot: tuple[uuid.UUID, uuid.UUID], run_id: uuid.UUID, user_id: Any, given: str, carried: Any
    ) -> None:
        """A go of the run begun, for its bot (its org's id and its own): with what the person said, or carried on
        with what they answered (`carried`)."""
        task = asyncio.create_task(self._run(*bot, run_id, user_id, given, carried))
        self.tasks[task] = run_id
        task.add_done_callback(lambda t: self.tasks.pop(t, None))

    def stop(self, run_id: uuid.UUID) -> None:
        """The run's go on this machine, cancelled (whether it runs or waits its turn)."""
        for task in [t for t, r in self.tasks.items() if r == run_id]:
            task.cancel()

    async def _go(self, bot: Any, run_id: uuid.UUID, user_id: uuid.UUID | None, given: str, carried: Any) -> None:
        if carried is None:
            message = prompt.task(bot, given)
        else:
            message = await carry.on(self, bot, run_id, *carried)
        await agent_run.go(self, bot, run_id, message, orchestrator.tools(self, bot, user_id))

    async def _run(
        self, org_id: uuid.UUID, bot_id: uuid.UUID, run_id: uuid.UUID, user_id: Any, given: str, carried: Any
    ) -> None:
        async with self.gate:
            try:
                await self._go(await self.bot(org_id, bot_id), run_id, user_id, given, carried)
            except Ask as ask:  # a bot the orchestrator asked asks again: the orchestrator's run waits again
                await runs.put(self.engine, org_id, run_id, status="needs_input", question=ask.question)
            except (BotError, GlyphhError) as err:
                await self._failed(org_id, run_id, err.message)
            except Exception as err:
                log.exception("bot run %s failed", run_id)
                await self._failed(org_id, run_id, f"The run failed: {type(err).__name__}: {err}")
        await self._woken(org_id, run_id)

    async def _failed(self, org_id: uuid.UUID, run_id: uuid.UUID, why: str) -> None:
        await runs.failed(self.engine, org_id, run_id, why)
        await session.drop(self.engine, org_id, run_id)

    async def _woken(self, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """A run of the orchestrator that waits on this run (a bot it asked, answered where that bot's own run
        waits) is carried on now that this one is over."""
        parent = await runs.parent(self.engine, org_id, run_id)
        if parent is not None and await runs.queue(self.engine, org_id, parent.id):
            carried: Carried = (dict(parent.question), None, parent.user_id)
            self.spawn((org_id, parent.bot_id), parent.id, parent.user_id, "", carried)

    async def wait(self) -> None:
        """Every go started here, finished (the tests')."""
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def close(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
