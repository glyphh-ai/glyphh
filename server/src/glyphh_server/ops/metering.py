"""Hosted machines metered per second at Fly's rates, by the time that passed: each tick, every hosted machine adds
the whole seconds since it was last metered (since it was made, the first time), and its `metered_at` moves on by
exactly those seconds, the fraction carried, its row locked while it does. A tick late, missed, run twice or in two
processes, or the server restarting, meters each second once. Its month adds its size's rate for those seconds while
it is started (its state at the tick) and its volume's GB for all of them, started or stopped: the cost, in
micro-dollars; and the charge, the cost with the org's markup (its own, else its plan's; none on a plan with no
hosting, Free, where the cost of machines held past the plan, their disks, is kept and nothing charged). The seconds
go to the month of the tick. A region with no rates is logged and costs nothing for those seconds."""

import logging
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import Row, case, func, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import MachineMonth, Org, PlanVersion, Rrotor, User
from glyphh_server.models.rrotor import SIZES
from glyphh_server.obs.logs import fields
from glyphh_server.ops.link.presence import ONLINE
from glyphh_server.ops.rates import SECONDS_PER_MONTH, VOLUME, InForce, in_force
from glyphh_server.ops.runtimes import month_of

log = logging.getLogger("glyphh.billing")

MICROS: Decimal = Decimal(1_000_000)

HOSTED = (
    select(Rrotor.id, Rrotor.name, Rrotor.size, Rrotor.region, Rrotor.state, User.org_id)
    .add_columns(func.coalesce(Rrotor.metered_at, Rrotor.created_at).label("since"))
    .add_columns(func.coalesce(Org.markup_pct, PlanVersion.hosting_markup_pct).label("markup_pct"))
    .join(User, User.id == Rrotor.user_id)
    .join(Org, Org.id == User.org_id)
    .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
    .where(Rrotor.mode == "hosted")
    .with_for_update(of=Rrotor)
)


def micros(usd: Decimal) -> int:
    return int((usd * MICROS).to_integral_value(ROUND_HALF_EVEN))


def priced(row: Row, rates: InForce, seconds: int) -> tuple[int, int]:
    """One machine's seconds: (cost, charge) in micro-dollars."""
    started = seconds if row.state == ONLINE else 0
    usd = rates.usd[row.size] * started + rates.usd[VOLUME] * SIZES[row.size].volume_gb * seconds
    cost = usd / SECONDS_PER_MONTH
    if row.markup_pct is None:  # a plan with no hosting (Free): the cost is kept, nothing is charged
        return micros(cost), 0
    return micros(cost), micros(cost * (1 + Decimal(row.markup_pct) / 100))


async def meter(conn: AsyncConnection, now: datetime, region: str) -> None:
    """Every hosted machine metered up to `now`, its online seconds this month tallied; a machine with no region is
    in the server's own."""
    found: dict[str, InForce | None] = {}
    for row in list(await conn.execute(HOSTED)):
        seconds = max(0, int((now - row.since).total_seconds()))
        if seconds == 0:
            continue
        await _tally(conn, row, month_of(now), seconds)
        where = row.region or region
        if where not in found:
            found[where] = await in_force(conn, where, now.date())
        rates = found[where]
        if rates is None:
            log.warning("no fly rates: machine not metered", extra=fields(runtime=str(row.id), region=where))
            continue
        cost, charge = priced(row, rates, seconds)
        await _add(conn, row, month_of(now), cost, charge)


async def _tally(conn: AsyncConnection, row: Row, month: str, seconds: int) -> None:
    """Its online seconds this month (from 0 once the month turned), and its time metered `seconds` further."""
    online = seconds if row.state == ONLINE else 0
    since = case((Rrotor.month == month, Rrotor.month_seconds), else_=0)
    moved = {"month": month, "month_seconds": since + online, "metered_at": row.since + timedelta(seconds=seconds)}
    await conn.execute(update(Rrotor).where(Rrotor.id == row.id).values(**moved))


async def _add(conn: AsyncConnection, row: Row, month: str, cost: int, charge: int) -> None:
    named = {"org_id": row.org_id, "name": row.name, "size": row.size}
    made = upsert(MachineMonth).values(rrotor_id=row.id, month=month, cost_micros=cost, charge_micros=charge, **named)
    added = {
        "cost_micros": MachineMonth.cost_micros + cost,
        "charge_micros": MachineMonth.charge_micros + charge,
        "updated_at": func.now(),
    }
    keys = [MachineMonth.rrotor_id, MachineMonth.month]
    await conn.execute(made.on_conflict_do_update(index_elements=keys, set_=named | added))
