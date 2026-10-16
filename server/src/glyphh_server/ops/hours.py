"""The hosted hours: every online runtime's month is tallied each minute against its plan's hours. Past them, the
runtime is paused (`pause` down its link, so rrotor answers 402; its machine stopped) until the month turns, when
every tally starts again and a paused runtime is resumed."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Row, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Rrotor, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.hosted import stop_idle
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.link.protocol import Pause, Resume
from glyphh_server.ops.plans import org_version
from glyphh_server.ops.runtimes import NOT_LINKED, month_of

log = logging.getLogger("glyphh.runtime")

HOSTED = (
    select(Rrotor.id, User.org_id, Rrotor.fly_machine_id, Rrotor.month, Rrotor.month_seconds, Rrotor.paused_at)
    .join(User, User.id == Rrotor.user_id)
    .where(Rrotor.mode == "hosted")
)


async def _count(engine: AsyncEngine, hub: Hub, row: Row, month: str, now: datetime, step: int) -> bool:
    """One runtime's tally brought up to now; True when it was paused this time."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, row.org_id)
        state = (await conn.execute(select(Rrotor.state).where(Rrotor.id == row.id))).scalar()
        seconds, was_paused = row.month_seconds, row.paused_at is not None
        values: dict[str, object] = {"month": month}
        if row.month != month:  # the month turned: the tally starts again, a paused runtime runs again
            seconds, was_paused, values["paused_at"] = 0, False, None
            if row.paused_at is not None:
                await hub.deliver(row.id, Resume().model_dump(mode="json"))
        if state == ONLINE:
            seconds += step
        allowed = (await org_version(conn, row.org_id)).runtime_hours
        over = allowed is not None and seconds >= allowed * 3600 and not was_paused
        if over:
            await hub.deliver(row.id, Pause().model_dump(mode="json"))
            values |= {"paused_at": now, "state": NOT_LINKED}
        await conn.execute(update(Rrotor).where(Rrotor.id == row.id).values(**values, month_seconds=seconds))
    return over


async def tally(engine: AsyncEngine, fly: Fly, hub: Hub, step: int) -> list[uuid.UUID]:
    """Every hosted runtime's month counts `step` more seconds while online; answers the runtimes paused this time,
    each one's machine stopped (a stop Fly refuses is logged: the pause holds either way)."""
    now = datetime.now(UTC)
    paused: list[uuid.UUID] = []
    async with engine.connect() as conn:  # the connecting role: every org's runtimes
        rows = list(await conn.execute(HOSTED))
    for row in rows:
        if not await _count(engine, hub, row, month_of(now), now, step):
            continue
        paused.append(row.id)
        try:
            await fly.stop(str(row.fly_machine_id))
        except Exception:
            log.exception("paused runtime not stopped", extra=fields(runtime=str(row.id)))
        log.info("runtime paused: the month's hours are spent", extra=fields(runtime=str(row.id)))
    return paused


async def tend(engine: AsyncEngine, fly: Fly, hub: Hub, idle: timedelta, step: int) -> None:
    """One tick of the server's care of hosted runtimes: the hours tallied, the idle ones stopped."""
    await tally(engine, fly, hub, step)
    await stop_idle(engine, fly, idle)
