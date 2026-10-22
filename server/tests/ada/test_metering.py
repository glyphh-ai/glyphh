"""Ada Cloud's metering (docs/specs/ada-cloud.md, section 7): reads counted in Redis flushed to ada_usage by the minute
tick; reads past a metered plan's month (Pro, Team) reported to Stripe's ada_requests meter, written before sent and
counted once, the metered price added to a subscription made before it; Checkout selling it; going down to Free
reporting it first. Stripe is faked at the HTTP layer, as everywhere in the suite."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import requests
from glyphh_server.app import create_app
from glyphh_server.models import AdaMeterEvent, AdaUsage, Org
from glyphh_server.ops import tend
from glyphh_server.ops.billing import ada_meter
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.link.hub import Hub
from tests.ada.conftest import ADA, pinned
from tests.conftest import REDIS_URL, _client
from tests.db.helpers import Person, person, subscribed
from tests.fakes import FakeStripe, fake_http

API: str = "http://api.test"


@pytest.fixture
async def billed(engine: AsyncEngine, stripe: FakeStripe, vector: None) -> AsyncIterator[httpx.AsyncClient]:
    """The server with Ada Cloud on and Stripe faked."""
    async for c in _client(create_app(ADA, http=fake_http(stripe))):
        c.base_url = httpx.URL(API)
        yield c


@pytest.fixture
async def counts() -> AsyncIterator[Redis]:
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


def meter(stripe: FakeStripe, name: str = "ada_requests") -> StripeClient:
    return StripeClient(fake_http(stripe), "sk_test", "glyphh_hosting", name)


def sent(stripe: FakeStripe, customer: str) -> list[dict[str, str]]:
    return [
        b for _, p, b in stripe.calls if p == "/billing/meter_events" and b["payload[stripe_customer_id]"] == customer
    ]


async def metered_org(engine: AsyncEngine, stripe: FakeStripe, cap: int = 2) -> tuple[Person, str]:
    """A Pro-like org whose reads past `cap` a month are metered, subscribed (before Ada Cloud: no metered item)."""
    who = await person(engine, "Pro")
    await pinned(engine, who.org_id, cloud_requests=cap, cloud_overage=True)
    customer, sub = f"cus_{who.org_id.hex}", f"sub_{who.org_id.hex}"
    await subscribed(engine, who.org_id, sub, customer)
    stripe.sub(sub, customer, "price_test_pro", 1)
    return who, customer


async def made(engine: AsyncEngine, org: uuid.UUID, month: str, n: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(insert(AdaUsage).values(org_id=org, period=month, requests=n))


async def test_the_tick_adds_what_redis_counted_to_the_database(engine: AsyncEngine, counts: Redis) -> None:
    org, month = (await person(engine, "Team")).org_id, requests.period()
    await counts.set(requests.pending_key(org, month), 5)
    await counts.sadd(requests.orgs_key(month), str(org))
    last = requests.before(month)
    await counts.set(requests.pending_key(org, last), 2)
    await counts.sadd(requests.orgs_key(last), str(org))
    assert await requests.flush(engine, counts) >= 7
    async with engine.connect() as conn:
        rows = dict(
            (await conn.execute(select(AdaUsage.period, AdaUsage.requests).where(AdaUsage.org_id == org))).all()
        )
    assert rows == {month: 5, last: 2}
    await counts.incrby(requests.pending_key(org, month), 3)
    await requests.flush(engine, counts)
    async with engine.connect() as conn:
        assert await requests.kept(conn, org, month) == 8
    assert str(org) in await counts.smembers(requests.orgs_key(month))  # this month's stays: a read may come
    assert str(org) not in await counts.smembers(requests.orgs_key(last))  # last month's is told and done
    gone = str(uuid.uuid4())  # an org removed since its reads were counted
    await counts.set(requests.pending_key(gone, month), 4)
    await counts.sadd(requests.orgs_key(month), gone)
    await requests.flush(engine, counts)
    assert gone not in await counts.smembers(requests.orgs_key(month))


async def test_reads_past_the_month_are_reported_once_and_priced(engine: AsyncEngine, stripe: FakeStripe) -> None:
    who, customer = await metered_org(engine, stripe)
    month = requests.period()
    await made(engine, who.org_id, month, 5)
    assert await ada_meter.report(engine, meter(stripe), "price_test_ada") >= 1
    (event,) = sent(stripe, customer)
    assert (event["event_name"], event["payload[value]"]) == ("ada_requests", "3")
    items = [i["price"]["id"] for i in stripe.subs[f"sub_{who.org_id.hex}"]["items"]["data"]]
    assert items == ["price_test_pro", "price_test_ada"]  # the metered price added once
    async with engine.connect() as conn:
        row = (await conn.execute(select(AdaMeterEvent).where(AdaMeterEvent.org_id == who.org_id))).one()
    assert event["identifier"] == str(row.id) and row.sent_at is not None and row.period == month
    async with engine.begin() as conn:
        await conn.execute(update(AdaUsage).where(AdaUsage.org_id == who.org_id).values(requests=7))
    await ada_meter.report(engine, meter(stripe), "price_test_ada")  # within the day: not yet
    assert len(sent(stripe, customer)) == 1
    stripe.meter_down = True
    assert await ada_meter.report(engine, meter(stripe), "price_test_ada", only=who.org_id) == 0
    stripe.meter_down = False
    await ada_meter.report(engine, meter(stripe), "price_test_ada")  # the unsent one, again, with its identifier
    second = sent(stripe, customer)
    assert [e["payload[value]"] for e in second] == ["3", "2", "2"] and second[1]["identifier"] == second[2][
        "identifier"
    ]
    calls = len(stripe.calls)
    await ada_meter.report(engine, meter(stripe), "price_test_ada", only=who.org_id)  # nothing due
    assert len(stripe.calls) == calls
    stale = (await _due(engine, who.org_id))[0]
    assert await ada_meter._write(engine, stale, datetime.now(UTC)) == []  # worked out again: nothing


async def _due(engine: AsyncEngine, org: uuid.UUID) -> list:  # type: ignore[type-arg]
    async with engine.connect() as conn:
        return list(await conn.execute(ada_meter.DUE.where(Org.id == org)))


async def test_a_month_ended_is_reported_at_once(engine: AsyncEngine, stripe: FakeStripe) -> None:
    who, customer = await metered_org(engine, stripe, cap=1)
    month = requests.period()
    await made(engine, who.org_id, month, 4)
    await ada_meter.report(engine, meter(stripe), None)  # no price set: the subscription left as it is
    assert [i["price"]["id"] for i in stripe.subs[f"sub_{who.org_id.hex}"]["items"]["data"]] == ["price_test_pro"]
    await made(engine, who.org_id, requests.before(month), 10)
    await ada_meter.report(engine, meter(stripe), None)  # within the day, but that month has ended
    assert [e["payload[value]"] for e in sent(stripe, customer)] == ["3", "9"]
    assert await ada_meter.report(engine, meter(stripe, ""), None) == 0  # no meter named: nothing reported
    row = types_row(month, None)
    assert ada_meter.due_now(row, datetime.now(UTC)) is True
    row = types_row(month, datetime.now(UTC) - timedelta(hours=1))
    assert ada_meter.due_now(row, datetime.now(UTC)) is False


def types_row(month: str, last: datetime | None) -> object:
    return type("Row", (), {"period": month, "last": last})()


async def test_checkout_sells_the_metered_reads_and_going_free_reports_them(
    engine: AsyncEngine, billed: httpx.AsyncClient, stripe: FakeStripe
) -> None:
    buyer = await person(engine, "Free")
    async with engine.begin() as conn:
        values = {"stripe_customer_id": f"cus_{buyer.org_id.hex}"}
        await conn.execute(update(Org).where(Org.id == buyer.org_id).values(**values))
    opened = await billed.post("/v1/billing/checkout", json={"plan": "Team"}, headers=buyer.headers)
    assert opened.status_code == 200, opened.text
    lines = {v for k, v in stripe.calls[-1][2].items() if k.endswith("[price]")}
    assert lines == {"price_test_team", "price_test_hosting", "price_test_ada"}
    basic = await billed.post("/v1/billing/checkout", json={"plan": "Basic"}, headers=buyer.headers)
    assert basic.status_code == 200, basic.text  # Basic's reads past its month are metered too; it has no hosting
    lines = {v for k, v in stripe.calls[-1][2].items() if k.endswith("[price]")}
    assert lines == {"price_test_basic", "price_test_ada"}
    unpriced = ADA.model_copy(update={"stripe_price_ada": None})
    async for other in _client(create_app(unpriced, http=fake_http(stripe))):
        refused = await other.post(f"{API}/v1/billing/checkout", json={"plan": "Pro"}, headers=buyer.headers)
        assert (refused.status_code, refused.json()["error"]["reason"]) == (503, "billing_off")
    who, customer = await metered_org(engine, stripe)
    await made(engine, who.org_id, requests.period(), 6)
    down = await billed.post("/v1/billing/plan", json={"plan": "Free"}, headers=who.headers)
    assert down.status_code == 200, down.text
    assert [e["payload[value]"] for e in sent(stripe, customer)] == ["4"]
    assert stripe.subs[f"sub_{who.org_id.hex}"]["status"] == "canceled"


async def test_the_tick_flushes_and_reports_with_ada_cloud_on(
    engine: AsyncEngine, stripe: FakeStripe, counts: Redis
) -> None:
    who, customer = await metered_org(engine, stripe, cap=1)
    month = requests.period()
    await counts.set(requests.pending_key(who.org_id, month), 3)
    await counts.sadd(requests.orgs_key(month), str(who.org_id))
    assert await tend.tend(engine, Hub(counts), ADA, 60, None, None)  # no Stripe: flushed only
    assert sent(stripe, customer) == []
    assert await tend.tend(engine, Hub(counts), ADA, 60, None, meter(stripe))
    assert [e["payload[value]"] for e in sent(stripe, customer)] == ["2"]
