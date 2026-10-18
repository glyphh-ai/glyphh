"""The minute tick runs in one process at a time: a Postgres advisory lock held for the tick, a process that finds it
held skipping that minute; and every machine is metered once for each second, however many ticks run."""

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import MachineMonth, Rrotor
from glyphh_server.ops import tend
from glyphh_server.ops.link.hub import Hub
from tests.api.test_hosting_usage import micros
from tests.conftest import SETTINGS
from tests.db.helpers import person
from tests.link import hosted_runtime


async def _a_minute_ago(engine: AsyncEngine) -> Any:
    """A small machine on Pro, started, last metered a minute ago by the database's clock."""
    rt = await hosted_runtime(engine, await person(engine, "Pro"), "ticked", "small")
    async with engine.begin() as conn:
        values = {"state": "online", "metered_at": func.now() - timedelta(seconds=60)}
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(**values))
    return rt


async def _metered(engine: AsyncEngine, rt: Any) -> tuple[int, int]:
    async with engine.connect() as conn:
        seconds = (await conn.execute(select(Rrotor.month_seconds).where(Rrotor.id == rt.id))).scalar_one()
        cost = await conn.execute(select(MachineMonth.cost_micros).where(MachineMonth.rrotor_id == rt.id))
        return seconds, cost.scalar_one_or_none() or 0


async def _tick(engine: AsyncEngine, redis: Redis) -> bool:
    return await tend.tend(engine, Hub(redis), SETTINGS, 60, None, None)


async def test_two_ticks_at_once_meter_each_machine_one_minute(engine: AsyncEngine, redis: Redis) -> None:
    rt = await _a_minute_ago(engine)
    ran = await asyncio.gather(_tick(engine, redis), _tick(engine, redis), _tick(engine, redis))
    assert True in ran
    assert await _metered(engine, rt) == (60, micros("7.15", 60))  # small's $6.70 started and its 3 GB, once


async def test_a_tick_another_process_holds_is_skipped(
    engine: AsyncEngine, redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    rt = await _a_minute_ago(engine)
    async with engine.connect() as other:  # another server process, mid-tick
        assert (await other.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": tend.TICK})).scalar_one()
        assert not await _tick(engine, redis)
        assert await _metered(engine, rt) == (0, 0)
        await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": tend.TICK})
    assert "tick skipped: another process is ticking" in caplog.text
    assert await _tick(engine, redis)  # its tick done: this one runs, and meters the minute it missed
    assert await _metered(engine, rt) == (60, micros("7.15", 60))


async def test_a_tick_that_fails_lets_go_of_the_lock(
    engine: AsyncEngine, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fails(*_: Any) -> None:
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(tend, "tally", fails)
    with pytest.raises(RuntimeError):
        await _tick(engine, redis)
    async with engine.connect() as other:
        assert (await other.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": tend.TICK})).scalar_one()
        await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": tend.TICK})
