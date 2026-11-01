"""Ada Cloud's reads past a metered plan's month (Basic, Pro, Team: cloud_overage), reported to Stripe's ada_requests
Billing Meter, one unit a read, priced $1 per 10,000 (GLYPHH_STRIPE_PRICE_ADA): for each subscribed org, the reads
past its plan's cloud_requests in each month (ada_usage, as the minute tick last flushed it) not yet reported, once a
day and as soon as the month has ended (and at once when the org goes down to Free). Each report is written before it
is sent, its id the identifier Stripe counts once, sent again at the next tick if Stripe would not take it. The
subscription is given the metered price first when it has none (one made before Ada Cloud)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Row, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.requests import period
from glyphh_server.errors import Unavailable
from glyphh_server.models import AdaMeterEvent, AdaUsage, Org, PlanVersion
from glyphh_server.obs.logs import fields
from glyphh_server.ops.billing.stripe import StripeClient

log = logging.getLogger("glyphh.billing")

EVERY: timedelta = timedelta(days=1)


def _reported(org_id: object, month: object) -> object:
    sent = select(func.coalesce(func.sum(AdaMeterEvent.requests), 0))
    return sent.where(AdaMeterEvent.org_id == org_id, AdaMeterEvent.period == month).scalar_subquery()


def _last(org_id: object) -> object:
    return select(func.max(AdaMeterEvent.created_at)).where(AdaMeterEvent.org_id == org_id).scalar_subquery()


DUE = (
    select(
        Org.id,
        Org.stripe_customer_id,
        Org.stripe_subscription_id,
        AdaUsage.period,
        (AdaUsage.requests - PlanVersion.cloud_requests - _reported(Org.id, AdaUsage.period)).label("due"),
        _last(Org.id).label("last"),
    )
    .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
    .join(AdaUsage, AdaUsage.org_id == Org.id)
    .where(Org.stripe_subscription_id.is_not(None), Org.stripe_customer_id.is_not(None))
    .where(PlanVersion.cloud_overage, PlanVersion.cloud_requests.is_not(None))
)


def due_now(row: Row, now: datetime) -> bool:
    """A day since the org's last report (or none yet), or the month ended."""
    return row.last is None or now - row.last >= EVERY or row.period < period(now)


async def _write(engine: AsyncEngine, row: Row, now: datetime) -> list[uuid.UUID]:
    """The report written, its due worked out again with the org's row locked: two servers ticking at once report it
    once."""
    async with engine.begin() as conn:
        await conn.execute(select(Org.id).where(Org.id == row.id).with_for_update())
        again = (await conn.execute(DUE.where(Org.id == row.id, AdaUsage.period == row.period))).first()
        if again is None or int(again.due) <= 0:
            return []
        values = {"org_id": row.id, "customer": row.stripe_customer_id, "period": row.period, "at": now}
        made = insert(AdaMeterEvent).values(**values, requests=int(again.due)).returning(AdaMeterEvent.id)
        return [(await conn.execute(made)).scalar_one()]


async def priced(stripe: StripeClient, sub_id: str, price: str | None) -> None:
    """The subscription carries the metered reads' price (a subscription made before Ada Cloud does not yet)."""
    if price is None:
        return
    items = (await stripe.subscription(sub_id))["items"]["data"]
    if not any(item["price"]["id"] == price for item in items):
        await stripe.change(sub_id, [{"price": price}])


async def _send(engine: AsyncEngine, stripe: StripeClient, event_id: uuid.UUID) -> bool:
    async with engine.connect() as conn:
        event = (await conn.execute(select(AdaMeterEvent).where(AdaMeterEvent.id == event_id))).one()
    at = int(event.at.timestamp())
    try:
        await stripe.meter_event(event.customer, event.requests, str(event.id), at, stripe.ada_meter)
    except Unavailable:
        log.warning("ada meter event not sent: again next tick", extra=fields(org=str(event.org_id)))
        return False
    async with engine.begin() as conn:
        await conn.execute(update(AdaMeterEvent).where(AdaMeterEvent.id == event_id).values(sent_at=func.now()))
    return True


async def report(engine: AsyncEngine, stripe: StripeClient, price: str | None, only: uuid.UUID | None = None) -> int:
    """Every report not yet sent sent again, then each org's reads past its month due now; `only`, that org's
    whatever the time. Answers how many Stripe took."""
    if not stripe.ada_meter:
        return 0
    now = datetime.now(UTC)
    async with engine.connect() as conn:  # the connecting role: every org's
        unsent = select(AdaMeterEvent.id).where(AdaMeterEvent.sent_at.is_(None))
        events = list((await conn.execute(unsent)).scalars())
        rows = list(await conn.execute(DUE if only is None else DUE.where(Org.id == only)))
    for row in rows:
        if int(row.due) <= 0 or (only is None and not due_now(row, now)):
            continue
        made = await _write(engine, row, now)
        await priced(stripe, row.stripe_subscription_id, price if made else None)  # only when a report was made
        events += made
    return sum([await _send(engine, stripe, e) for e in events])
