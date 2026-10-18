"""Hosting reported to Stripe's Billing Meter (one unit, one US cent): for each org with a subscription, the cents
its machines have charged and not yet reported, once a day and as its period ends (and at once when it goes down to
Free). Each report is written before it is sent, its id the identifier Stripe counts once; one Stripe would not take
is sent again, with the same identifier, at the next tick. What is under a cent is carried, as the charge is summed
from the start."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Row, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Unavailable
from glyphh_server.models import MachineMonth, MeterEvent, Org
from glyphh_server.obs.logs import fields
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.usage import MICROS_PER_CENT

log = logging.getLogger("glyphh.billing")

EVERY: timedelta = timedelta(days=1)
PERIOD_END: timedelta = timedelta(minutes=10)  # this close to its renewal, an org's hosting is reported


def _owed(org_id: object) -> object:
    charged = select(func.coalesce(func.sum(MachineMonth.charge_micros), 0)).where(MachineMonth.org_id == org_id)
    return charged.scalar_subquery()


def _reported(org_id: object) -> object:
    return select(func.coalesce(func.sum(MeterEvent.cents), 0)).where(MeterEvent.org_id == org_id).scalar_subquery()


def _last(org_id: object) -> object:
    return select(func.max(MeterEvent.created_at)).where(MeterEvent.org_id == org_id).scalar_subquery()


ORGS = select(
    Org.id,
    Org.stripe_customer_id,
    Org.renews_at,
    (func.div(_owed(Org.id), MICROS_PER_CENT) - _reported(Org.id)).label("due"),
    _last(Org.id).label("last"),
).where(Org.stripe_subscription_id.is_not(None), Org.stripe_customer_id.is_not(None))


def due_now(org: Row, now: datetime) -> bool:
    """A day since the last report (or none yet), or the period's end come since it."""
    if org.last is None or now - org.last >= EVERY:
        return True
    edge = None if org.renews_at is None else org.renews_at - PERIOD_END
    return edge is not None and org.last < edge <= now


async def _write(engine: AsyncEngine, org_id: uuid.UUID, now: datetime) -> list[uuid.UUID]:
    """The org's report written, its due worked out again with its row locked: two servers ticking at once report it
    once. Nothing when nothing is due by then."""
    async with engine.begin() as conn:
        await conn.execute(select(Org.id).where(Org.id == org_id).with_for_update())
        org = (await conn.execute(ORGS.where(Org.id == org_id))).first()
        if org is None or int(org.due) <= 0:
            return []
        made = insert(MeterEvent).values(org_id=org_id, customer=org.stripe_customer_id, cents=int(org.due), at=now)
        return [(await conn.execute(made.returning(MeterEvent.id))).scalar_one()]


async def _send(engine: AsyncEngine, stripe: StripeClient, event_id: uuid.UUID) -> bool:
    async with engine.connect() as conn:
        event = (await conn.execute(select(MeterEvent).where(MeterEvent.id == event_id))).one()
    try:
        await stripe.meter_event(event.customer, event.cents, str(event.id), int(event.at.timestamp()))
    except Unavailable:
        log.warning("meter event not sent: again next tick", extra=fields(org=str(event.org_id), event=str(event.id)))
        return False
    async with engine.begin() as conn:
        await conn.execute(update(MeterEvent).where(MeterEvent.id == event_id).values(sent_at=func.now()))
    return True


async def report(engine: AsyncEngine, stripe: StripeClient, only: uuid.UUID | None = None) -> int:
    """Every report not yet sent sent again, then each org's hosting due now; `only`, that org's whatever the time.
    Answers how many Stripe took."""
    if not stripe.meter:
        return 0
    now = datetime.now(UTC)
    async with engine.connect() as conn:  # the connecting role: every org's
        unsent = list((await conn.execute(select(MeterEvent.id).where(MeterEvent.sent_at.is_(None)))).scalars())
        orgs = list(await conn.execute(ORGS if only is None else ORGS.where(Org.id == only)))
    events = unsent
    for org in orgs:
        if int(org.due) <= 0 or (only is None and not due_now(org, now)):
            continue
        events += await _write(engine, org.id, now)
    return sum([await _send(engine, stripe, e) for e in events])
