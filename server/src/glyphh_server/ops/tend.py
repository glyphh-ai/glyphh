"""The server's minute tick, with or without hosting on: every hosted machine metered at Fly's rates up to now, its
online seconds this month tallied (ops/metering.py), the keys that expired taken off their runtimes, the Enterprise
grants past their date ended (their hosting due reported first), the idle machines and those held past their plan
stopped, and the hosting due reported to Stripe's meter (ops/billing/meter.py).

Every server process runs the tick, and production runs more than one: a tick takes a Postgres advisory lock (TICK)
on a connection it holds for the tick, and a process that finds it held skips that minute, so no two ticks ever run
at once. Ticks one after another in different processes may both run in the same minute; every part is safe to run
again: the meter counts the time since each machine was last metered, never a fixed step."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.ops.billing.meter import report
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.enterprise import expire
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.held import hold
from glyphh_server.ops.idle import stop_idle
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.metering import meter
from glyphh_server.ops.runtime_keys import push_expired

log = logging.getLogger("glyphh.runtime")

TICK: int = 0x67_6C_74_6B  # one tick at a time across every server process


async def tally(engine: AsyncEngine, region: str, now: datetime | None = None) -> None:
    """Every hosted machine metered and its month tallied up to `now`, else the database's clock: one clock for every
    process."""
    async with engine.begin() as conn:  # the connecting role: every org's runtimes
        await meter(conn, now or (await conn.execute(text("SELECT now()"))).scalar_one(), region)


async def tend(
    engine: AsyncEngine, hub: Hub, settings: Settings, step: int, fly: Fly | None, stripe: StripeClient | None
) -> bool:
    """One tick, if no other process is ticking: answers whether it ran."""
    async with engine.connect() as held:
        if not (await held.execute(text("SELECT pg_try_advisory_lock(:lock)"), {"lock": TICK})).scalar_one():
            log.info("tick skipped: another process is ticking")
            return False
        await held.commit()  # a session lock: held past the transaction, until unlocked or the connection ends
        try:
            await _tick(engine, hub, settings, step, fly, stripe)
        finally:
            await held.execute(text("SELECT pg_advisory_unlock(:lock)"), {"lock": TICK})
    return True


async def _tick(
    engine: AsyncEngine, hub: Hub, settings: Settings, step: int, fly: Fly | None, stripe: StripeClient | None
) -> None:
    """The month tallied and metered, the keys that expired since the last tick (with a tick to spare) taken off
    their runtimes, the Enterprise grants past their date ended (with Stripe, their hosting due reported first); with
    hosting on, the idle machines stopped and those held past their plan stopped; with Stripe, the hosting due
    reported to its meter."""
    await tally(engine, settings.fly_region)
    await push_expired(engine, hub, timedelta(seconds=2 * step))
    await expire(engine, stripe)
    if fly is not None:
        await stop_idle(engine, fly, timedelta(minutes=settings.runtime_idle_minutes))
        async with engine.begin() as conn:  # the connecting role: every org's
            await hold(conn, fly)
    if stripe is not None:
        await report(engine, stripe)
