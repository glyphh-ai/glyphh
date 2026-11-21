"""The bots on this machine (app.state.bots): Pipedream, the Claude client, and the runs, each a background task in the
server's own process, a few at once (bot_runs_at_once; the rest wait their turn, queued). Started, a run is committed
queued before its task begins, so its page finds it at once. At the server's start, the runs this machine was running
when it stopped are failed: nothing resumes them."""

import asyncio
import logging
import uuid
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Unavailable
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import loop, runs, store, tools
from glyphh_server.ops.bots.pipedream import Pipedream
from glyphh_server.ops.bots.views import RunView

log = logging.getLogger("glyphh.bots")
OFF: str = "Bots are not set up on this server (no Anthropic API key)."


class Bots:
    def __init__(self, engine: AsyncEngine, redis: Redis, settings: Settings, http: httpx.AsyncClient, ada: Any):
        self.engine, self.redis, self.settings, self.ada = engine, redis, settings, ada
        self.pd = Pipedream(http, settings)
        self.claude: Any = None  # the AsyncAnthropic, made at the first run (a test sets its own)
        self.gate = asyncio.Semaphore(settings.bot_runs_at_once)
        self.tasks: set[asyncio.Task[None]] = set()

    def client(self) -> Any:
        if self.claude is None:
            if not self.settings.anthropic_api_key:
                raise Unavailable(OFF, reason="anthropic_off")
            from anthropic import AsyncAnthropic  # its own HTTP stack (httpx2), apart from the server's

            self.claude = AsyncAnthropic(api_key=self.settings.anthropic_api_key)
        return self.claude

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

    async def start(self, who: Principal, slug: str, given: str) -> RunView:
        """A run of the bot, queued: it starts when one of this machine's places is free."""
        client = self.client()
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            bot = await store.row(conn, slug)
        made = await runs.create(self.engine, who.org_id, bot, who.user_id, given)
        task = asyncio.create_task(self._run(client, who, bot, made.id, given))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return made

    async def _run(self, client: Any, who: Principal, bot: Any, run_id: uuid.UUID, given: str) -> None:
        async with self.gate:
            try:
                offered = await tools.offered(self.pd, self.engine, self.ada, who, bot)
            except Exception as err:
                log.exception("bot run %s: its tools could not be read", run_id)
                said = getattr(err, "message", None) or f"{type(err).__name__}: {err}"
                await runs.finish(self.engine, bot.org_id, run_id, "", f"Its tools could not be read: {said}")
                return
            await loop.go(loop.Run(self, client, who, bot, run_id, offered, given))

    async def wait(self) -> None:
        """Every run started here, finished (the tests')."""
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    async def close(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
        if self.claude is not None:
            await self.claude.close()
