"""Hosting reported to Stripe's Billing Meter: the cents an org's machines charged and not yet reported, once a day
and as its period ends, written before it is sent so a retry is counted once, what is under a cent carried; and all
of it at once when the org goes down to Free."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import MachineMonth, MeterEvent, Org
from glyphh_server.ops.billing.meter import _write, due_now, report
from glyphh_server.ops.billing.stripe import StripeClient
from tests.db.helpers import Person, person, subscribed
from tests.fakes import FakeStripe, fake_http


async def _charged(engine: AsyncEngine, who: Person, micros: int, month: str = "2026-10") -> None:
    async with engine.begin() as conn:
        values = {"rrotor_id": uuid.uuid4(), "month": month, "org_id": who.org_id, "name": "m", "size": "small"}
        await conn.execute(insert(MachineMonth).values(**values, cost_micros=micros, charge_micros=micros))


async def _events(engine: AsyncEngine, who: Person) -> list[tuple[int, bool]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(MeterEvent.cents, MeterEvent.sent_at).where(MeterEvent.org_id == who.org_id).order_by(MeterEvent.at)
        )
        return [(r.cents, r.sent_at is not None) for r in rows]


def _sent(stripe: FakeStripe, customer: str) -> list[dict[str, str]]:
    return [
        b for _, p, b in stripe.calls if p == "/billing/meter_events" and b["payload[stripe_customer_id]"] == customer
    ]


async def _age(engine: AsyncEngine, who: Person, by: timedelta) -> None:
    async with engine.begin() as conn:
        older = {"created_at": MeterEvent.created_at - by}
        await conn.execute(update(MeterEvent).where(MeterEvent.org_id == who.org_id).values(**older))


async def test_hosting_is_reported_once_a_day_the_remainder_carried(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine, "Pro")
    customer = f"cus_{ada.org_id.hex}"
    await subscribed(engine, ada.org_id, f"sub_{ada.org_id.hex}", customer)
    meter = StripeClient(fake_http(stripe), "sk_test", "glyphh_hosting")
    await _charged(engine, ada, 1_234_567)  # $1.234567: 123 cents now, the rest carried
    await _charged(engine, ada, 5_000, "2026-09")
    await report(engine, meter)
    (event,) = _sent(stripe, customer)
    assert (event["event_name"], event["payload[value]"]) == ("glyphh_hosting", "123")
    async with engine.connect() as conn:
        row = (await conn.execute(select(MeterEvent).where(MeterEvent.org_id == ada.org_id))).one()
    assert event["identifier"] == str(row.id) and event["timestamp"] == str(int(row.at.timestamp()))
    await _charged(engine, ada, 10_000)
    await report(engine, meter)  # within the day: not yet
    assert len(_sent(stripe, customer)) == 1
    await _age(engine, ada, timedelta(days=1))
    await report(engine, meter)
    assert [e["payload[value]"] for e in _sent(stripe, customer)] == ["123", "1"]  # 124.9567 cents, 124 reported
    assert await _events(engine, ada) == [(123, True), (1, True)]


async def test_a_report_stripe_refused_is_sent_again_with_its_identifier(
    engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team")
    customer = f"cus_{ada.org_id.hex}"
    await subscribed(engine, ada.org_id, f"sub_{ada.org_id.hex}", customer)
    meter = StripeClient(fake_http(stripe), "sk_test", "glyphh_hosting")
    await _charged(engine, ada, 990_000)
    stripe.meter_down = True
    await report(engine, meter)
    assert await _events(engine, ada) == [(99, False)]
    stripe.meter_down = False
    await report(engine, meter)
    first, again = _sent(stripe, customer)
    assert first["identifier"] == again["identifier"] and await _events(engine, ada) == [(99, True)]
    assert await report(engine, StripeClient(fake_http(stripe), "sk_test", "")) == 0  # no meter: nothing reported
    assert await _write(engine, ada.org_id, datetime.now(UTC)) == []  # all reported: nothing written
    assert await _write(engine, uuid.uuid4(), datetime.now(UTC)) == []


def test_the_period_end_is_reported_as_it_comes() -> None:
    now = datetime(2026, 10, 18, 12, tzinfo=UTC)

    def org(last: datetime | None, renews: datetime | None) -> object:
        return type("Org", (), {"last": last, "renews_at": renews})()

    hour_ago = now - timedelta(hours=1)
    assert due_now(org(None, None), now) and due_now(org(now - timedelta(days=1), None), now)
    assert not due_now(org(hour_ago, None), now)
    assert due_now(org(hour_ago, now + timedelta(minutes=5)), now)  # its renewal ten minutes off: reported now
    assert not due_now(org(hour_ago, now + timedelta(hours=2)), now)
    assert not due_now(org(now - timedelta(minutes=1), now + timedelta(minutes=5)), now)  # reported for it already


async def test_going_down_to_free_reports_the_hosting_first(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    customer, sub = f"cus_{ada.org_id.hex}", f"sub_{ada.org_id.hex}"
    stripe.sub(sub, customer, "price_test_pro", 1)
    await subscribed(engine, ada.org_id, sub, customer)
    await _charged(engine, ada, 250_000)
    await report(engine, StripeClient(fake_http(stripe), "sk_test", "glyphh_hosting"))
    await _charged(engine, ada, 70_000)  # within the day: due, but not yet reported
    res = await client.post("/v1/billing/plan", json={"plan": "Free"}, headers=ada.headers)
    assert res.status_code == 200, res.text
    paths = [p for _, p, _ in stripe.calls]
    assert paths[-2:] == ["/billing/meter_events", f"/subscriptions/{sub}"]
    assert [e["payload[value]"] for e in _sent(stripe, customer)] == ["25", "7"]
    async with engine.connect() as conn:
        assert (await conn.execute(select(Org.stripe_subscription_id).where(Org.id == ada.org_id))).scalar() is None
