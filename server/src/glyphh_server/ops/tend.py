"""The server's minute tick, with or without hosting on: every online machine's month counts the minute, every machine
is metered at Fly's rates (ops/metering.py), the idle ones and those held past their plan are stopped, the keys that
expired are taken off their runtimes, the Enterprise grants past their date are ended, and the hosting due is
reported to Stripe's meter (ops/billing/meter.py). No plan has hosted hours: a machine is never paused."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.models import Rrotor
from glyphh_server.ops.billing.meter import report
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.enterprise import expire
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.held import hold
from glyphh_server.ops.idle import stop_idle
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.metering import meter
from glyphh_server.ops.runtime_keys import push_expired
from glyphh_server.ops.runtimes import month_of


async def tally(engine: AsyncEngine, step: int, region: str) -> None:
    """Every hosted machine's month brought up to now: `step` more seconds while online, from 0 once it turned."""
    month = month_of(datetime.now(UTC))
    online = case((Rrotor.state == ONLINE, step), else_=0)
    since = case((Rrotor.month == month, Rrotor.month_seconds), else_=0)
    async with engine.begin() as conn:  # the connecting role: every org's runtimes
        hosted = select(Rrotor.id).where(Rrotor.mode == "hosted")
        await conn.execute(
            update(Rrotor).where(Rrotor.id.in_(hosted)).values(month=month, month_seconds=since + online)
        )
        await meter(conn, step, region)


async def tend(
    engine: AsyncEngine, hub: Hub, settings: Settings, step: int, fly: Fly | None, stripe: StripeClient | None
) -> None:
    """One tick: the month tallied and metered, the keys that expired since the last tick (with a tick to spare)
    taken off their runtimes, the Enterprise grants past their date ended; with hosting on, the idle machines stopped
    and those held past their plan stopped; with Stripe, the hosting due reported to its meter."""
    await tally(engine, step, settings.fly_region)
    await push_expired(engine, hub, timedelta(seconds=2 * step))
    await expire(engine)
    if fly is not None:
        await stop_idle(engine, fly, timedelta(minutes=settings.runtime_idle_minutes))
        async with engine.begin() as conn:  # the connecting role: every org's
            await hold(conn, fly)
    if stripe is not None:
        await report(engine, stripe)
