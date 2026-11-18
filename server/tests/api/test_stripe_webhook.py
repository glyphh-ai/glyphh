"""Stripe's webhook keeps orgs true while the old subscriptions end: plan version, status, Stripe ids, and a top-up
paid late. The subscription is only ever read from Stripe. Unsigned events are refused."""

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import LlmBalance, LlmLedger, Org, Plan, PlanVersion
from glyphh_server.ops.billing.signature import sign
from tests.conftest import SETTINGS, WEBHOOK_SECRET, _client
from tests.db.helpers import org_row, person, plan_version, subscribed
from tests.fakes import FakeStripe, fake_http

# The plans are seeded without Stripe prices (db/seed.py): production's versions carry them, so these tests give two.
PRO: str = "price_test_pro_webhook"
TEAM: str = "price_test_team_webhook"


@pytest.fixture(scope="module", autouse=True)
async def prices(engine: AsyncEngine) -> AsyncIterator[None]:
    async def price(plan: str, price_id: str | None) -> None:
        async with engine.begin() as conn:
            version = PlanVersion.id == await plan_version(conn, plan)
            await conn.execute(update(PlanVersion).where(version).values(stripe_price_id=price_id))

    await price("Pro", PRO)
    await price("Team", TEAM)
    yield
    await price("Pro", None)
    await price("Team", None)


async def _send(client: httpx.AsyncClient, event: dict[str, Any], secret: str = WEBHOOK_SECRET) -> httpx.Response:
    body = json.dumps(event).encode()
    headers = {"stripe-signature": sign(secret, body, int(time.time())), "content-type": "application/json"}
    return await client.post("/v1/stripe/webhook", content=body, headers=headers)


def _event(kind: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {"id": "evt_1", "type": kind, "data": {"object": obj}}


def _ids(kind: str) -> tuple[str, str]:
    """A subscription and a customer nobody else has."""
    return f"sub_{kind}_{uuid.uuid4().hex[:8]}", f"cus_{kind}_{uuid.uuid4().hex[:8]}"


async def _plan(engine: AsyncEngine, org_id: Any) -> tuple[str, str, str | None]:
    row = await org_row(engine, org_id)
    async with engine.connect() as conn:
        on = select(Plan.name).join(PlanVersion, PlanVersion.plan_id == Plan.id)
        name = (await conn.execute(on.where(PlanVersion.id == row.plan_version_id))).scalar_one()
    return name, row.billing_status, row.stripe_subscription_id


async def test_a_finished_checkout_puts_the_org_on_its_plan_its_metered_item_passing(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe, caplog: pytest.LogCaptureFixture
) -> None:
    ada = await person(engine)
    sub, customer = _ids("new")
    stripe.sub(sub, customer, TEAM, 1)["items"]["data"][0]["current_period_end"] = 1_800_000_000
    stripe.add_item(sub, "price_test_reads")
    obj = {"mode": "subscription", "client_reference_id": str(ada.org_id), "customer": customer, "subscription": sub}
    with caplog.at_level(logging.WARNING, logger="glyphh.billing"):
        res = await _send(client, _event("checkout.session.completed", obj))
    assert res.status_code == 204 and res.content == b""
    assert not [r for r in caplog.records if r.name == "glyphh.billing"]  # the metered item is no unknown price
    assert await _plan(engine, ada.org_id) == ("Team", "active", sub)
    org = await org_row(engine, ada.org_id)
    assert org.stripe_customer_id == customer
    assert org.renews_at == datetime.fromtimestamp(1_800_000_000, UTC)
    assert datetime.now(UTC) - org.first_paid_at < timedelta(minutes=1)
    assert stripe.calls == [("GET", f"/subscriptions/{sub}")]  # read, never written


async def test_subscription_changes_are_read_fresh_and_a_deleted_one_returns_the_org_to_free(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team")
    sub, customer = _ids("live")
    await subscribed(engine, ada.org_id, sub, customer)
    ending = stripe.sub(sub, customer, PRO, 1, "past_due")
    ending.update(current_period_end=1_800_000_000, cancel_at_period_end=True)
    stale = {"id": sub, "customer": customer, "metadata": {}, "status": "active"}
    assert (await _send(client, _event("customer.subscription.updated", stale))).status_code == 204
    assert await _plan(engine, ada.org_id) == ("Pro", "past_due", sub)
    org = await org_row(engine, ada.org_id)
    assert org.renews_at is None and org.first_paid_at is None  # ending at the period's end; never seen paid
    ending.update(cancel_at_period_end=False)  # an older Stripe version: the period's end is on the subscription
    await _send(client, _event("customer.subscription.updated", stale))
    assert (await org_row(engine, ada.org_id)).renews_at == datetime.fromtimestamp(1_800_000_000, UTC)
    stripe.sub(sub, customer, PRO, 1, "canceled")
    await _send(client, _event("customer.subscription.deleted", stale))
    assert await _plan(engine, ada.org_id) == ("Free", "canceled", None)
    org = await org_row(engine, ada.org_id)
    assert (org.renews_at, org.plan_until, org.stripe_customer_id) == (None, None, customer)
    assert [method for method, _ in stripe.calls] == ["GET", "GET", "GET"]


async def test_the_first_payment_is_kept_as_when_the_org_first_paid(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    sub, customer = _ids("paid")
    await subscribed(engine, ada.org_id, sub, customer)
    stripe.sub(sub, customer, PRO)
    old_style = {"customer": customer, "subscription": sub}
    assert (await _send(client, _event("invoice.payment_succeeded", old_style))).status_code == 204
    first = (await org_row(engine, ada.org_id)).first_paid_at
    assert first is not None and await _plan(engine, ada.org_id) == ("Pro", "active", sub)
    assert (await org_row(engine, ada.org_id)).renews_at is None  # Stripe gave no period end
    stripe.sub(sub, customer, TEAM)
    new_style = {"customer": customer, "parent": {"subscription_details": {"subscription": sub, "metadata": {}}}}
    await _send(client, _event("invoice.payment_succeeded", new_style))
    assert await _plan(engine, ada.org_id) == ("Team", "active", sub)
    assert (await org_row(engine, ada.org_id)).first_paid_at == first


async def test_the_org_is_found_by_the_id_it_was_given_when_stripe_has_no_customer_of_ours(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe, caplog: pytest.LogCaptureFixture
) -> None:
    ada, eve = await person(engine), await person(engine, "Pro")
    sub, customer = _ids("meta")
    stripe.sub(sub, customer, "price_unknown", 2, "weird_status")
    obj = {"id": sub, "customer": customer, "metadata": {"org_id": str(ada.org_id)}}
    with caplog.at_level(logging.WARNING, logger="glyphh.billing"):
        await _send(client, _event("customer.subscription.created", obj))
    assert await _plan(engine, ada.org_id) == ("Free", "none", sub)
    assert (await org_row(engine, ada.org_id)).first_paid_at is None
    unknown = [r.fields for r in caplog.records if r.getMessage() == "unknown stripe price"]  # type: ignore[attr-defined]
    assert unknown == [{"org": str(ada.org_id), "price": "price_unknown"}]
    theirs, payer = _ids("invoice")
    stripe.sub(theirs, payer, TEAM)
    details = {"subscription": theirs, "metadata": {"org_id": str(eve.org_id)}}
    paid = {"customer": payer, "parent": {"subscription_details": details}}
    await _send(client, _event("invoice.payment_succeeded", paid))
    assert await _plan(engine, eve.org_id) == ("Team", "active", theirs)


async def test_an_enterprise_deals_subscription_keeps_its_plan_until_it_ends(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe, caplog: pytest.LogCaptureFixture
) -> None:
    ada = await person(engine, "Enterprise")
    sub, customer = _ids("deal")
    await subscribed(engine, ada.org_id, sub, customer)
    async with engine.begin() as conn:
        until = datetime(2027, 11, 1, tzinfo=UTC)
        await conn.execute(update(Org).where(Org.id == ada.org_id).values(plan_until=until))
    deal = stripe.sub(sub, customer, "price_deal")
    deal["items"]["data"] += [{"id": "si_pro", "price": {"id": PRO}}, {"id": "si_team", "price": {"id": TEAM}}]
    obj = {"id": sub, "customer": customer}
    with caplog.at_level(logging.WARNING, logger="glyphh.billing"):
        await _send(client, _event("customer.subscription.updated", obj))
    assert await _plan(engine, ada.org_id) == ("Pro", "active", sub)  # the first plan item it knows; the rest logged
    unknown = [r.fields["price"] for r in caplog.records if r.getMessage() == "unknown stripe price"]  # type: ignore[attr-defined]
    assert unknown == ["price_deal", TEAM]
    stripe.sub(sub, customer, "price_deal")
    async with engine.begin() as conn:
        enterprise = await plan_version(conn, "Enterprise")
        await conn.execute(update(Org).where(Org.id == ada.org_id).values(plan_version_id=enterprise))
    await _send(client, _event("customer.subscription.updated", obj))
    assert await _plan(engine, ada.org_id) == ("Enterprise", "active", sub)  # no plan item: the plan stays
    assert (await org_row(engine, ada.org_id)).plan_until == until
    stripe.sub(sub, customer, "price_deal", 1, "incomplete_expired")
    await _send(client, _event("customer.subscription.updated", obj))
    assert await _plan(engine, ada.org_id) == ("Free", "incomplete_expired", None)
    assert (await org_row(engine, ada.org_id)).plan_until is None


async def test_events_for_no_org_another_subscription_or_of_no_interest_change_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe, caplog: pytest.LogCaptureFixture
) -> None:
    ada = await person(engine, "Pro")
    sub, customer = _ids("current")
    await subscribed(engine, ada.org_id, sub, customer)
    stripe.sub("sub_old", customer, TEAM, 9, "canceled")
    nobody = "00000000-0000-0000-0000-000000000000"
    with caplog.at_level(logging.INFO, logger="glyphh.billing"):
        for event in (
            _event("customer.subscription.deleted", {"id": "sub_old", "customer": customer}),
            _event("customer.subscription.updated", {"id": "sub_x", "customer": "cus_nobody"}),
            _event(
                "customer.subscription.updated",
                {"id": "sub_x", "customer": "cus_nobody", "metadata": {"org_id": "bad"}},
            ),
            _event("customer.subscription.updated", {"id": "sub_x", "metadata": {"org_id": nobody}}),
            _event("customer.subscription.updated", {"customer": customer}),
            _event("checkout.session.completed", {"mode": "setup", "customer": customer}),
            _event("checkout.session.async_payment_succeeded", {"mode": "subscription", "customer": customer}),
            _event("invoice.paid", {"customer": customer}),
            _event("invoice.payment_succeeded", {"customer": customer}),
            {"type": "ping"},
            {},
        ):
            assert (await _send(client, event)).status_code == 204, event
    assert await _plan(engine, ada.org_id) == ("Pro", "active", sub)
    said = [r.getMessage() for r in caplog.records if r.name == "glyphh.billing"]
    no_org, ignored = "stripe event for no org", "stripe event ignored"
    assert said == ["stale subscription ignored", *[no_org] * 4, *[ignored] * 3, no_org, *[ignored] * 2]
    assert stripe.calls == [("GET", "/subscriptions/sub_old")]


def _topup(org_id: Any, cents: int, session: str, **over: Any) -> dict[str, Any]:
    paid = {"id": session, "mode": "payment", "client_reference_id": str(org_id), "amount_total": cents}
    return {**paid, "metadata": {"kind": "llm_topup"}, "payment_status": "paid", "currency": "usd", **over}


async def _held(engine: AsyncEngine, org_id: Any) -> tuple[int | None, list[tuple[str, int, str | None]]]:
    """The org's balance, and its ledger."""
    async with engine.connect() as conn:
        balance = (await conn.execute(select(LlmBalance.micros).where(LlmBalance.org_id == org_id))).scalar()
        entries = select(LlmLedger.kind, LlmLedger.amount_micros, LlmLedger.stripe_ref)
        ledger = await conn.execute(entries.where(LlmLedger.org_id == org_id).order_by(LlmLedger.at))
        return balance, [tuple(row) for row in ledger]


async def test_a_top_up_paid_late_is_credited_once_for_its_session(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe, caplog: pytest.LogCaptureFixture
) -> None:
    ada = await person(engine)
    first, second = f"cs_{uuid.uuid4().hex}", f"cs_{uuid.uuid4().hex}"
    for kind, session in (
        ("checkout.session.completed", _topup(ada.org_id, 2_500, f"{first}_unpaid", payment_status="unpaid")),
        ("checkout.session.completed", _topup(ada.org_id, 2_500, f"{first}_eur", currency="eur")),
        ("checkout.session.completed", _topup(ada.org_id, 2_500, f"{first}_other", metadata=None)),
        ("checkout.session.completed", _topup(uuid.uuid4(), 9_900, f"{first}_nobody")),
        ("checkout.session.completed", _topup("not-an-org", 9_900, f"{first}_bad")),
    ):
        assert (await _send(client, _event(kind, session))).status_code == 204, session
    assert await _held(engine, ada.org_id) == (None, [])
    with caplog.at_level(logging.WARNING, logger="glyphh.billing"):
        for _ in range(2):  # sent again: credited once
            paid = _event("checkout.session.async_payment_succeeded", _topup(ada.org_id, 2_500, first))
            assert (await _send(client, paid)).status_code == 204
    assert await _held(engine, ada.org_id) == (25_000_000, [("topup", 25_000_000, first)])
    owed = [r for r in caplog.records if r.getMessage() == "top-up paid after the wind-down: owed back"]
    assert [r.fields for r in owed] == [{"org": str(ada.org_id), "session": first}]  # type: ignore[attr-defined]
    customer = _ids("topup")[1]
    await subscribed(engine, ada.org_id, _ids("topup")[0], customer)
    by_customer = _topup(None, 1_000, second, client_reference_id=None, customer=customer)
    await _send(client, _event("checkout.session.completed", by_customer))
    balance, ledger = await _held(engine, ada.org_id)
    assert balance == 35_000_000 and ledger[-1] == ("topup", 10_000_000, second)
    assert stripe.calls == []  # a top-up reads nothing from Stripe


async def test_an_unsigned_wrongly_signed_or_old_event_is_refused(client: httpx.AsyncClient) -> None:
    body = json.dumps(_event("invoice.paid", {})).encode()
    now = int(time.time())
    old = sign(WEBHOOK_SECRET, body, now - 3600)
    other_body = sign(WEBHOOK_SECRET, b"{}", now)
    for header in (None, "", "t=abc,v1=x", "v1=only", f"t={now}", sign("whsec_other", body, now), other_body, old):
        headers = {} if header is None else {"stripe-signature": header}
        res = await client.post("/v1/stripe/webhook", content=body, headers=headers)
        assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED", header
    rotated = f"{sign('whsec_other', body, now)},{sign(WEBHOOK_SECRET, body, now).split(',')[1]}"
    assert (
        await client.post("/v1/stripe/webhook", content=body, headers={"stripe-signature": rotated})
    ).status_code == 204


async def test_stripe_not_answering_is_unavailable_and_changes_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    sub, customer = _ids("down")
    await subscribed(engine, ada.org_id, sub, customer)
    stripe.sub(sub, customer, PRO, 1, "canceled")
    stripe.fail = True
    res = await _send(client, _event("customer.subscription.deleted", {"id": sub, "customer": customer}))
    assert res.status_code == 503
    assert (res.json()["error"]["code"], res.json()["error"]["reason"]) == ("E_UNAVAILABLE", "stripe")
    assert await _plan(engine, ada.org_id) == ("Pro", "active", sub)
    stripe.fail = False  # Stripe sends it again
    assert (await _send(client, _event("customer.subscription.deleted", {"id": sub, "customer": customer}))).is_success
    assert await _plan(engine, ada.org_id) == ("Free", "canceled", None)


async def test_without_stripes_keys_the_webhook_is_unavailable(engine: AsyncEngine) -> None:
    no_secret = SETTINGS.model_copy(update={"stripe_webhook_secret": ""})
    async for off in _client(create_app(no_secret, http=fake_http())):
        hook = await off.post("/v1/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})
        assert hook.status_code == 503 and hook.json()["error"]["reason"] == "billing_off"
    no_key = SETTINGS.model_copy(update={"stripe_secret_key": ""})
    async for off in _client(create_app(no_key, http=fake_http())):
        hook = await _send(off, {"type": "ping"})
        assert hook.status_code == 503 and hook.json()["error"]["reason"] == "billing_off"
