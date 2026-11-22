"""What one go of a bot's runner needs, gathered on the server's loop before the worker thread starts: the bot, its
program (its scoped tools, ready to call), its Ada (by its own key) and its Claude (the org's own Anthropic key, or
Glyphh's; metered on either, ops/bots/prices.py; at the bot's effort, ops/bots/access.py); and the go itself, its
state kept on the bot after."""

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
from glyphh_server.ops.bots import access, cloud, decided, engine, keys, prices
from glyphh_server.ops.bots.pipedream import Pipedream

NO_KEY: str = "Add your Anthropic API key in the bots' settings: its agent steps run on it."


def _ada(base: str) -> Callable[[str], Any]:
    def made(key: str) -> Any:
        from glyphh import Ada

        return Ada(base, key)

    return made


def _claude(key: str, model: str, effort: str | None = None) -> Any:
    """Agent steps on the Claude API with this key, each request carrying the bot's effort (ops/bots/access.py)."""
    import anthropic

    client = anthropic.Anthropic(api_key=key, max_retries=3)
    return ApiClaude(model=model, client=access.WithEffort(client, effort))


class Goes:
    def __init__(self, engine_: AsyncEngine, redis: Redis, settings: Settings, http: httpx.AsyncClient):
        self.engine, self.redis, self.settings = engine_, redis, settings
        self.pd = Pipedream(http, settings)
        self.ada_for: Callable[[str], Any] = _ada(settings.ada_base)  # a bot's Ada, by its key (a test sets a fake)
        # agent steps, by key, model and effort (a test sets a fake)
        self.claude_for: Callable[[str, str, str | None], Any] = _claude
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
        """The bot's Claude, metered on either key (the markup alone on the org's own), and whether it is the org's."""
        own = await self.own_key(bot.org_id)
        if not own and not self.settings.anthropic_api_key:
            raise Unavailable(NO_KEY, reason="anthropic_off")
        priced = prices.charged(bot.model, own_key=bool(own))

        async def admit() -> Any:
            return await meter.admit(self.engine, self.redis, self.settings, bot.org_id)

        async def record(admitted: Any, got: Any) -> int:
            return await meter.record(self.engine, admitted, priced, got.input_tokens, got.output_tokens)

        effort = getattr(bot, "effort", None)  # the maker's own steps have none: the model's default
        inner = self.claude_for(own or self.settings.anthropic_api_key, bot.model, effort)
        return engine.Metered(inner, asyncio.get_running_loop(), admit, record), bool(own)

    async def go(self, bot: Any, act: Callable[[Runner], Any], claude: Any = None) -> engine.Left:
        """One go of the bot's runner in a worker thread; the state it leaves kept on the bot."""
        loop = asyncio.get_running_loop()
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, bot.org_id)
            made, asked = await cloud.calls(self.pd, conn, bot)
        program, bot = cloud.Program(made, loop), cloud.guarded(bot, asked)
        ada = self.ada_for(unseal(self.settings.secret_key, bot.ada_key))
        left = await asyncio.to_thread(engine.go, bot, program, ada, claude, act)
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, bot.org_id)
            await conn.execute(update(Bot).where(Bot.id == bot.id).values(state=left.state))
            await decided.sync(conn, bot, left.state)
        return left
