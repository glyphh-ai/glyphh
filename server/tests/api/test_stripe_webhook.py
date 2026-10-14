"""Stripe's webhook keeps orgs true: plan version, seats, status, Stripe ids. Unsigned events are refused."""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.ops.billing.signature import sign
from tests.conftest import SETTINGS, WEBHOOK_SECRET, _client
from tests.db.helpers import org_row, person, subscribed
from tests.fakes import FakeStripe, fake_http


async def _send(client: httpx.AsyncClient, event: dict[str, Any], secret: str = WEBHOOK_SECRET) -> httpx.Response:
    body = json.dumps(event).encode()
    headers = {"stripe-signature": sign(secret, body, int(time.time())), "content-type": "application/json"}
    return await client.post("/v1/stripe/webhook", content=body, headers=headers)


def _event(kind: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {"id": "evt_1", "type": kind, "data": {"object": obj}}


async def _plan(engine: AsyncEngine, org_id: Any) -> tuple[str, int, str, str | None]:
    from glyphh_server.ops.plans import org_version

    row = await org_row(engine, org_id)
    async with engine.connect() as conn:
        name = (await org_version(conn, org_id)).name
    return name, row.seats, row.billing_status, row.stripe_subscription_id


async def test_a_finished_checkout_puts_the_org_on_its_plan_and_seats(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    stripe.sub("sub_new", "cus_new", "price_test_team", 4)
    obj = {
        "mode": "subscription",
        "client_reference_id": str(ada.org_id),
        "customer": "cus_new",
        "subscription": "sub_new",
    }
    assert (await _send(client, _event("checkout.session.completed", obj))).status_code == 204
    assert await _plan(engine, ada.org_id) == ("Team", 4, "active", "sub_new")
    assert (await org_row(engine, ada.org_id)).stripe_customer_id == "cus_new"


async def test_subscription_changes_are_read_fresh_and_a_deleted_one_returns_the_org_to_free(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team", seats=3)
    await subscribed(engine, ada.org_id, "sub_live", "cus_live")
    stripe.sub("sub_live", "cus_live", "price_test_pro", 1, "past_due")
    stale = {"id": "sub_live", "customer": "cus_live", "metadata": {}, "status": "active"}
    assert (await _send(client, _event("customer.subscription.updated", stale))).status_code == 204
    assert await _plan(engine, ada.org_id) == ("Pro", 1, "past_due", "sub_live")
    stripe.sub("sub_live", "cus_live", "price_test_pro", 1, "canceled")
    await _send(client, _event("customer.subscription.deleted", stale))
    assert await _plan(engine, ada.org_id) == ("Free", 1, "canceled", None)


async def test_the_org_is_found_by_metadata_when_stripe_has_no_customer_of_ours(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    stripe.sub("sub_meta", "cus_meta", "price_unknown", 2, "weird_status")
    obj = {"id": "sub_meta", "customer": "cus_meta", "metadata": {"org_id": str(ada.org_id)}}
    await _send(client, _event("customer.subscription.created", obj))
    assert await _plan(engine, ada.org_id) == ("Free", 2, "none", "sub_meta")


async def test_events_for_no_org_another_subscription_or_of_no_interest_change_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    await subscribed(engine, ada.org_id, "sub_current", "cus_current")
    stripe.sub("sub_old", "cus_current", "price_test_team", 9, "canceled")
    for event in (
        _event("customer.subscription.deleted", {"id": "sub_old", "customer": "cus_current"}),
        _event(
            "customer.subscription.updated", {"id": "sub_x", "customer": "cus_nobody", "metadata": {"org_id": "bad"}}
        ),
        _event(
            "customer.subscription.updated",
            {"id": "sub_x", "metadata": {"org_id": "00000000-0000-0000-0000-000000000000"}},
        ),
        _event("customer.subscription.updated", {"customer": "cus_current"}),
        _event("checkout.session.completed", {"mode": "payment", "customer": "cus_current"}),
        _event("invoice.paid", {"customer": "cus_current"}),
        {"type": "ping"},
    ):
        assert (await _send(client, event)).status_code == 204, event
    assert await _plan(engine, ada.org_id) == ("Pro", 1, "active", "sub_current")


async def test_an_unsigned_wrongly_signed_or_old_event_is_refused(client: httpx.AsyncClient) -> None:
    body = json.dumps(_event("invoice.paid", {})).encode()
    old = sign(WEBHOOK_SECRET, body, int(time.time()) - 3600)
    for header in (None, "t=abc,v1=x", "v1=only", sign("whsec_other", body, int(time.time())), old):
        headers = {} if header is None else {"stripe-signature": header}
        res = await client.post("/v1/stripe/webhook", content=body, headers=headers)
        assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED", header


@pytest.fixture
async def billing_off(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    off = SETTINGS.model_copy(update={"stripe_secret_key": "", "stripe_webhook_secret": ""})
    async for c in _client(create_app(off, http=fake_http())):
        yield c


async def test_without_stripe_keys_billing_is_unavailable(billing_off: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await billing_off.post("/v1/billing/portal", headers=ada.headers)
    assert res.status_code == 503 and res.json()["error"]["reason"] == "billing_off"
    hook = await billing_off.post("/v1/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})
    assert hook.status_code == 503
