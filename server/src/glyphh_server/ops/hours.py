"""The hosted hours: every online machine's month is tallied each minute, and a person's machines together against
their plan's hours. Past them, each of the person's machines is paused (`pause` down its link, so rrotor answers 402;
its machine stopped) until the month turns, when every tally starts again and a paused machine is resumed. A machine
made while the hours are spent is paused at the next tick."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from itertools import groupby

from sqlalchemy import Row, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Rrotor, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.idle import stop_idle
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.link.protocol import Pause, Resume
from glyphh_server.ops.plans import org_version
from glyphh_server.ops.runtime_keys import push_expired
from glyphh_server.ops.runtimes import FIRST, NOT_LINKED, month_of

Tally = tuple[Row, int, bool, dict[str, object]]

log = logging.getLogger("glyphh.runtime")

HOSTED = (
    select(Rrotor.id, Rrotor.user_id, User.org_id, Rrotor.fly_machine_id, Rrotor.month, Rrotor.month_seconds)
    .add_columns(Rrotor.paused_at)
    .join(User, User.id == Rrotor.user_id)
    .where(Rrotor.mode == "hosted")
    .order_by(Rrotor.user_id, *FIRST)
)


async def _tallied(conn: AsyncConnection, hub: Hub, rows: list[Row], month: str, step: int) -> list[Tally]:
    """Each machine's month brought up to now: (row, seconds, paused already, the values to write)."""
    ids = [r.id for r in rows]
    online = set((await conn.execute(select(Rrotor.id).where(Rrotor.id.in_(ids), Rrotor.state == ONLINE))).scalars())
    out: list[Tally] = []
    for row in rows:
        seconds, was_paused = row.month_seconds, row.paused_at is not None
        values: dict[str, object] = {"month": month}
        if row.month != month:  # the month turned: the tally starts again, a paused machine runs again
            seconds, was_paused, values["paused_at"] = 0, False, None
            if row.paused_at is not None:
                await hub.deliver(row.id, Resume().model_dump(mode="json"))
        out.append((row, seconds + (step if row.id in online else 0), was_paused, values))
    return out


async def _count(engine: AsyncEngine, hub: Hub, rows: list[Row], month: str, now: datetime, step: int) -> list[Row]:
    """One person's machines tallied; past the plan's hours, all of them together, each one not yet paused is paused.
    Answers the machines paused this time."""
    paused: list[Row] = []
    async with engine.begin() as conn:
        await tenancy.enter(conn, rows[0].org_id)
        tallies = await _tallied(conn, hub, rows, month, step)
        allowed = (await org_version(conn, rows[0].org_id)).runtime_hours
        over = allowed is not None and sum(t[1] for t in tallies) >= allowed * 3600
        for row, seconds, was_paused, values in tallies:
            if over and not was_paused:
                await hub.deliver(row.id, Pause().model_dump(mode="json"))
                values |= {"paused_at": now, "state": NOT_LINKED}
                paused.append(row)
            await conn.execute(update(Rrotor).where(Rrotor.id == row.id).values(**values, month_seconds=seconds))
    return paused


async def tally(engine: AsyncEngine, fly: Fly, hub: Hub, step: int) -> list[uuid.UUID]:
    """Every hosted machine's month counts `step` more seconds while online; answers the machines paused this time,
    each one stopped (a stop Fly refuses is logged: the pause holds either way)."""
    now = datetime.now(UTC)
    paused: list[uuid.UUID] = []
    async with engine.connect() as conn:  # the connecting role: every org's runtimes
        rows = list(await conn.execute(HOSTED))
    for _, mine in groupby(rows, key=lambda r: r.user_id):
        for row in await _count(engine, hub, list(mine), month_of(now), now, step):
            paused.append(row.id)
            try:
                await fly.stop(str(row.fly_machine_id))
            except Exception:
                log.exception("paused runtime not stopped", extra=fields(runtime=str(row.id)))
            log.info("runtime paused: the month's hours are spent", extra=fields(runtime=str(row.id)))
    return paused


async def tend(engine: AsyncEngine, fly: Fly, hub: Hub, idle: timedelta, step: int) -> None:
    """One tick of the server's care of hosted runtimes: the hours tallied, the idle ones stopped, and the keys that
    expired since the last tick (with a tick to spare) taken off their runtimes."""
    await tally(engine, fly, hub, step)
    await stop_idle(engine, fly, idle)
    await push_expired(engine, hub, timedelta(seconds=2 * step))
