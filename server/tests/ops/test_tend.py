"""The minute tick runs in one process at a time: a Postgres advisory lock held for the tick, a process that finds it
held skipping that minute; every part runs whatever another does and is safe to run again; and the app ticks every
minute, surviving a failure."""

import asyncio
import json
import time
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server import app as app_module
from glyphh_server.app import create_app
from glyphh_server.models import OpsEvent
from glyphh_server.obs import events_store, tick
from glyphh_server.obs.events import QUEUE
from glyphh_server.ops import tend
from glyphh_server.ops.cloudflare import Cloudflare
from tests.conftest import SETTINGS, _client
from tests.fakes import fake_http


async def _logged(redis: Redis, message: str) -> None:
    """An ops event waiting on Redis, as the handler leaves one."""
    line = {"at": time.time(), "severity": "warning", "kind": "tick", "source": "glyphh.tick", "message": message}
    await redis.rpush(QUEUE, json.dumps(line))  # type: ignore[misc]


async def _moved(engine: AsyncEngine, message: str) -> int:
    async with engine.connect() as conn:
        return len(list(await conn.execute(select(OpsEvent.id).where(OpsEvent.message == message))))


async def test_ticks_at_once_run_one_at_a_time_and_each_part_once(engine: AsyncEngine, redis: Redis) -> None:
    await redis.delete(tick.KEY)
    message = f"waiting {time.time()}"
    await _logged(redis, message)
    ran = await asyncio.gather(tend.tend(engine, redis), tend.tend(engine, redis), tend.tend(engine, redis))
    assert True in ran
    assert await tick.last(redis) is not None and await _moved(engine, message) == 1


async def test_a_tick_another_process_holds_is_skipped(
    engine: AsyncEngine, redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="glyphh.tick")
    await redis.delete(tick.KEY)
    message = f"held {time.time()}"
    await _logged(redis, message)
    async with engine.connect() as other:  # another server process, mid-tick
        assert (await other.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": tend.TICK})).scalar_one()
        assert not await tend.tend(engine, redis)
        assert await tick.last(redis) is None and await _moved(engine, message) == 0
        await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": tend.TICK})
    assert "tick skipped: another process is ticking" in caplog.text
    assert await tend.tend(engine, redis)  # its tick done: this one runs, and does what it missed
    assert await tick.last(redis) is not None and await _moved(engine, message) == 1


async def test_a_part_that_fails_is_logged_by_name_and_the_rest_run(
    engine: AsyncEngine, redis: Redis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def fails(*_: Any) -> None:
        raise RuntimeError("redis hiccup")

    async def fails_too(*_: Any) -> None:
        raise ValueError("cloudflare hiccup")

    monkeypatch.setattr(tick, "beat", fails)
    monkeypatch.setattr(tend.traffic, "hourly", fails_too)
    message = f"after a failure {time.time()}"
    await _logged(redis, message)
    with pytest.raises(RuntimeError, match="redis hiccup"):  # the first failure, raised once every part has run
        await tend.tend(engine, redis, Cloudflare(fake_http(), "cf-test-token"))
    assert "tick part failed: heartbeat" in caplog.text and "tick part failed: traffic" in caplog.text
    assert "tick part failed: ops events" not in caplog.text and await _moved(engine, message) == 1


async def test_a_tick_that_fails_lets_go_of_the_lock(
    engine: AsyncEngine, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fails(*_: Any) -> None:
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(events_store, "drain", fails)
    with pytest.raises(RuntimeError):
        await tend.tend(engine, redis)
    async with engine.connect() as other:
        assert (await other.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": tend.TICK})).scalar_one()
        await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": tend.TICK})


async def test_the_app_ticks_every_minute_and_survives_a_failure(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(app_module, "IDLE_EVERY", 0.01)
    ticks: list[Any] = []
    stopped = asyncio.Event()

    async def ticked(engine: AsyncEngine, redis: Redis, cf: Any) -> bool:
        ticks.append(cf)
        if len(ticks) == 1:
            raise RuntimeError("hiccup")
        stopped.set()
        return True

    monkeypatch.setattr(tend, "tend", ticked)
    settings = SETTINGS.model_copy(update={"cloudflare_api_token": "cf-test-token"})
    async for _ in _client(create_app(settings, http=fake_http())):
        await asyncio.wait_for(stopped.wait(), 5)
    assert "tick failed" in caplog.text and len(ticks) >= 2
    assert isinstance(ticks[0], Cloudflare) and ticks[0].headers == {"authorization": "Bearer cf-test-token"}


async def test_without_a_cloudflare_token_the_app_ticks_without_traffic(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "IDLE_EVERY", 0.01)
    ticked = asyncio.Event()
    given: list[Any] = []

    async def tick_once(engine: AsyncEngine, redis: Redis, cf: Any) -> bool:
        given.append(cf)
        ticked.set()
        return True

    monkeypatch.setattr(tend, "tend", tick_once)
    async for _ in _client(create_app(SETTINGS, http=fake_http())):
        await asyncio.wait_for(ticked.wait(), 5)
    assert given[0] is None
