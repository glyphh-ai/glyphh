"""What the bots' work needs, gathered on the server's loop: a bot's row, the Anthropic key its run is billed on (the
org's own, else Glyphh's), its Ada (by its own key), Claude for the bot maker (metered on either key,
ops/bots/prices.py), and a go of the SDK's runner on the bot's state in a worker thread (ops/bots/engine.py), its
state kept on the bot after and its decisions copied where they are read (ops/bots/decided.py)."""

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
from glyphh_server.ops.bots import access, decided, engine, keys, orchestrator, prices
from glyphh_server.ops.bots.agent import sdk
from glyphh_server.ops.bots.agent.turn import Agent
from glyphh_server.ops.bots.pipedream import Pipedream

NO_KEY: str = "Add your Anthropic API key in the bots' settings: your bots run on it."


def _ada(base: str) -> Callable[[str], Any]:
    def made(key: str) -> Any:
        from glyphh import Ada

        return Ada(base, key)

    return made


def _claude(key: str, model: str, effort: str | None = None) -> Any:
    """Claude on the API with this key, each request carrying an effort when one is given (ops/bots/access.py)."""
    import anthropic

    client = anthropic.Anthropic(api_key=key, max_retries=3)
    return ApiClaude(model=model, client=access.WithEffort(client, effort))


class Goes:
    def __init__(self, engine_: AsyncEngine, redis: Redis, settings: Settings, http: httpx.AsyncClient):
        self.engine, self.redis, self.settings = engine_, redis, settings
        self.pd = Pipedream(http, settings)
        self.ada_for: Callable[[str], Any] = _ada(settings.ada_base)  # a bot's Ada, by its key (a test sets a fake)
        self.claude_for: Callable[[str, str, str | None], Any] = _claude  # the maker's Claude (a test sets a fake)
        self.agent: Agent = sdk.run  # one turn of a bot's agent: the Agent SDK (a test sets a fake)
        self.check_key: keys.Check = keys.anthropic_check

    async def bot(self, org_id: uuid.UUID, bot_id: uuid.UUID) -> Any:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return (await conn.execute(select(Bot).where(Bot.id == bot_id))).one()

    async def own_key(self, org_id: uuid.UUID) -> str | None:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            return await keys.own(conn, self.settings.secret_key)

    async def key_of(self, bot: Any) -> tuple[str, bool]:
        """The Anthropic key the bot's run is billed on, and whether it is the org's own."""
        own = await self.own_key(bot.org_id)
        if not own and not self.settings.anthropic_api_key:
            raise Unavailable(NO_KEY, reason="anthropic_off")
        return own or self.settings.anthropic_api_key, bool(own)

    async def claude_of(self, bot: Any) -> tuple[Any, bool]:
        """Claude for the bot maker, metered on either key (the markup alone on the org's own), and whether it is
        the org's."""
        key, own = await self.key_of(bot)
        priced = prices.charged(bot.model, own_key=own)

        async def admit() -> Any:
            return await meter.admit(self.engine, self.redis, self.settings, bot.org_id)

        async def record(admitted: Any, got: Any) -> int:
            return await meter.record(self.engine, admitted, priced, got.input_tokens, got.output_tokens)

        inner = self.claude_for(key, bot.model, None)
        return engine.Metered(inner, asyncio.get_running_loop(), admit, record), own

    async def go(self, bot: Any, act: Callable[[Runner], Any]) -> engine.Left:
        """One go of the bot's runner in a worker thread, on the bot's state as it is now; the state it leaves kept
        on the bot."""
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, bot.org_id)
            bot = (await conn.execute(select(Bot).where(Bot.id == bot.id))).one()
            sealed = await orchestrator.keyed(conn, bot, self.settings.secret_key)
        ada = self.ada_for(unseal(self.settings.secret_key, sealed))
        left = await asyncio.to_thread(engine.go, bot, ada, act)
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, bot.org_id)
            await conn.execute(update(Bot).where(Bot.id == bot.id).values(state=left.state))
            await decided.sync(conn, bot, left.state)
        return left
