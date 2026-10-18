"""The server's minute tick for hosted runtimes: every online machine's month counts the minute, the idle ones are
stopped, and the keys that expired are taken off their runtimes. No plan has hosted hours: a machine is never paused."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Rrotor
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.idle import stop_idle
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.runtime_keys import push_expired
from glyphh_server.ops.runtimes import month_of


async def tally(engine: AsyncEngine, step: int) -> None:
    """Every hosted machine's month brought up to now: `step` more seconds while online, from 0 once it turned."""
    month = month_of(datetime.now(UTC))
    online = case((Rrotor.state == ONLINE, step), else_=0)
    since = case((Rrotor.month == month, Rrotor.month_seconds), else_=0)
    async with engine.begin() as conn:  # the connecting role: every org's runtimes
        hosted = select(Rrotor.id).where(Rrotor.mode == "hosted")
        await conn.execute(
            update(Rrotor).where(Rrotor.id.in_(hosted)).values(month=month, month_seconds=since + online)
        )


async def tend(engine: AsyncEngine, fly: Fly, hub: Hub, idle: timedelta, step: int) -> None:
    """One tick of the server's care of hosted runtimes: the month tallied, the idle ones stopped, and the keys that
    expired since the last tick (with a tick to spare) taken off their runtimes."""
    await tally(engine, step)
    await stop_idle(engine, fly, idle)
    await push_expired(engine, hub, timedelta(seconds=2 * step))
