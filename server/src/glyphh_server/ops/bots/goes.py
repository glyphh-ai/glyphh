"""What one go of a bot's runner needs, gathered on the server's loop before the worker thread starts: the bot, its
program (its scoped tools, ready to call), its Ada (by its own key) and its Claude (the org's own Anthropic key, or
Glyphh's metered); and the go itself, its state kept on the bot after."""

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from glyphh.bots import ApiClaude, Runner
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Unavailable
from glyphh_server.llm import meter
from glyphh_server.models import Bot
from glyphh_server.ops.auth.sealed import unseal
from glyphh_server.ops.bots import cloud, engine, keys, prices
from glyphh_server.ops.bots.pipedream import Pipedream

NO_KEY: str = "Add your Anthropic API key in the bots' settings: its agent steps run on it."


def _ada(base: str) -> Callable[[str], Any]:
    def made(key: str) -> Any:
        from glyphh import Ada

        return Ada(base, key)

    return made


def _claude(key: str, model: str) -> Any:
    return ApiClaude(api_key=key, model=model)


class Goes:
    def __init__(self, engine_: AsyncEngine, redis: Redis, settings: Settings, http: httpx.AsyncClient):
        self.engine, self.redis, self.settings = engine_, redis, settings
        self.pd = Pipedream(http, settings)
        self.ada_for: Callable[[str], Any] = _ada(settings.ada_base)  # a bot's Ada, by its key (a test sets a fake)
        self.claude_for: Callable[[str, str], Any] = _claude  # agent steps, by key and model (a test sets a fake)
        self.check_key: keys.Check = keys.anthropic_check

    async def bot(self, org_id: uuid.UUID, bot_id: uuid.UUID) -> Any:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return (await conn.execute(select(Bot).where(Bot.id == bot_id))).one()

    async def own_key(self, org_id: uuid.UUID) -> str | None:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return await keys.own(conn, self.settings.secret_key)

    async def claude_of(self, bot: Any) -> tuple[Any, bool]:
        """The bot's Claude, and whether it is on the org's own key."""
        own = await self.own_key(bot.org_id)
        if own:
            return self.claude_for(own, bot.model), True
        if not self.settings.anthropic_api_key:
            raise Unavailable(NO_KEY, reason="anthropic_off")
        priced = prices.model(bot.model)

        async def admit() -> Any:
            return await meter.admit(self.engine, self.redis, self.settings, bot.org_id)

        async def record(admitted: Any, got: Any) -> int:
            return await meter.record(self.engine, admitted, priced, got.input_tokens, got.output_tokens)

        inner = self.claude_for(self.settings.anthropic_api_key, bot.model)
        return engine.Metered(inner, asyncio.get_running_loop(), admit, record), False

    async def go(self, bot: Any, act: Callable[[Runner], Any], claude: Any = None) -> engine.Left:
        """One go of the bot's runner in a worker thread; the state it leaves kept on the bot."""
        loop = asyncio.get_running_loop()
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, bot.org_id)
            program = cloud.Program(await cloud.calls(self.pd, conn, bot), loop)
        ada = self.ada_for(unseal(self.settings.secret_key, bot.ada_key))
        left = await asyncio.to_thread(engine.go, bot, program, ada, claude, act)
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, bot.org_id)
            await conn.execute(update(Bot).where(Bot.id == bot.id).values(state=left.state))
        return left
