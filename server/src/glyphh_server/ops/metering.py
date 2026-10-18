"""Hosted machines metered per second at Fly's rates. Each minute every hosted machine's month adds its size's rate for
the seconds it was started and its volume's GB for every second, started or stopped: the cost, in micro-dollars; and
the charge, the cost with the org's markup (its own, else its plan's; none on a plan with no hosting, Free, where the
cost of machines held past the plan, their disks, is kept and nothing charged). A region with no rates is logged and
costs nothing that minute."""

import logging
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import Row, func, select
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
    .add_columns(func.coalesce(Org.markup_pct, PlanVersion.hosting_markup_pct).label("markup_pct"))
    .join(User, User.id == Rrotor.user_id)
    .join(Org, Org.id == User.org_id)
    .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
    .where(Rrotor.mode == "hosted")
)


def micros(usd: Decimal) -> int:
    return int((usd * MICROS).to_integral_value(ROUND_HALF_EVEN))


def priced(row: Row, rates: InForce, step: int) -> tuple[int, int]:
    """One machine's minute: (cost, charge) in micro-dollars."""
    started = step if row.state == ONLINE else 0
    usd = rates.usd[row.size] * started + rates.usd[VOLUME] * SIZES[row.size].volume_gb * step
    cost = usd / SECONDS_PER_MONTH
    if row.markup_pct is None:  # a plan with no hosting (Free): the cost is kept, nothing is charged
        return micros(cost), 0
    return micros(cost), micros(cost * (1 + Decimal(row.markup_pct) / 100))


async def meter(conn: AsyncConnection, step: int, region: str) -> None:
    """Every hosted machine's month brought up to now; a machine with no region is in the server's own."""
    now = datetime.now(UTC)
    found: dict[str, InForce | None] = {}
    for row in await conn.execute(HOSTED):
        where = row.region or region
        if where not in found:
            found[where] = await in_force(conn, where, now.date())
        rates = found[where]
        if rates is None:
            log.warning("no fly rates: machine not metered", extra=fields(runtime=str(row.id), region=where))
            continue
        cost, charge = priced(row, rates, step)
        await _add(conn, row, month_of(now), cost, charge)


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
