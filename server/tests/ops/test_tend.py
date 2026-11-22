"""The minute tick runs in one process at a time: a Postgres advisory lock held for the tick, a process that finds it
held skipping that minute; every part safe to run again; and the app ticks every minute, surviving a failure."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server import app as app_module
from glyphh_server.app import create_app
from glyphh_server.models import Org
from glyphh_server.ops import tend
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.plans import org_version
from tests.conftest import SETTINGS, _client
from tests.db.helpers import person
from tests.fakes import fake_http


async def _lapsed(engine: AsyncEngine) -> Any:
    """An org whose Enterprise grant ended a minute ago."""
    who = await person(engine, "Enterprise")
    async with engine.begin() as conn:
        values = {"plan_until": datetime.now(UTC) - timedelta(minutes=1)}
        await conn.execute(update(Org).where(Org.id == who.org_id).values(**values))
    return who


async def _plan(engine: AsyncEngine, who: Any) -> str:
    async with engine.connect() as conn:
        return (await org_version(conn, who.org_id)).name


async def _tick(engine: AsyncEngine, redis: Redis) -> bool:
    return await tend.tend(engine, Hub(redis), SETTINGS, 60, None)


async def test_ticks_at_once_run_one_at_a_time_and_each_part_once(engine: AsyncEngine, redis: Redis) -> None:
    who = await _lapsed(engine)
    ran = await asyncio.gather(_tick(engine, redis), _tick(engine, redis), _tick(engine, redis))
    assert True in ran
    assert await _plan(engine, who) == "Free"


async def test_a_tick_another_process_holds_is_skipped(
    engine: AsyncEngine, redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    who = await _lapsed(engine)
    async with engine.connect() as other:  # another server process, mid-tick
        assert (await other.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": tend.TICK})).scalar_one()
        assert not await _tick(engine, redis)
        assert await _plan(engine, who) == "Enterprise"
        await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": tend.TICK})
    assert "tick skipped: another process is ticking" in caplog.text
    assert await _tick(engine, redis)  # its tick done: this one runs, and does what it missed
    assert await _plan(engine, who) == "Free"


async def test_a_tick_that_fails_lets_go_of_the_lock(
    engine: AsyncEngine, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fails(*_: Any) -> None:
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(tend, "expire", fails)
    with pytest.raises(RuntimeError):
        await _tick(engine, redis)
    async with engine.connect() as other:
        assert (await other.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": tend.TICK})).scalar_one()
        await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": tend.TICK})


async def test_the_app_ticks_every_minute_and_survives_a_failure(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(app_module, "IDLE_EVERY", 0.01)
    ticks: list[int] = []
    stopped = asyncio.Event()

    async def ticked(
        engine: AsyncEngine, hub: Any, cfg: Any, step: int, stripe: Any, cf: Any, gh: Any, bots: Any
    ) -> None:
        assert stripe is not None and cf is not None and gh is not None and bots is not None
        ticks.append(step)
        if len(ticks) == 1:
            raise RuntimeError("hiccup")
        stopped.set()

    monkeypatch.setattr(tend, "tend", ticked)
    settings = SETTINGS.model_copy(update={"cloudflare_api_token": "cf-test-token", "github_traffic_token": "gh"})
    app = create_app(settings, http=fake_http())
    async for _ in _client(app):
        await asyncio.wait_for(stopped.wait(), 5)
    assert "tick failed" in caplog.text and len(ticks) >= 2
