"""Plans and billing: Checkout, plan changes, Stripe's portal, all against a fake Stripe."""

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Rrotor
from tests.db.helpers import member, org_row, person, subscribed
from tests.fakes import FakeStripe
from tests.link import hosted_runtime

FEATURES_OFF = {"sync": False, "ha": False, "offline": False, "sso": False}


async def test_the_plans_are_free_basic_pro_team_and_enterprise_never_naming_the_markup(
    client: httpx.AsyncClient,
) -> None:
    plans = (await client.get("/v1/plans")).json()
    assert [(p["name"], p["price_cents"], p["interval"], p["self_serve"]) for p in plans] == [
        ("Free", 0, None, True),
        ("Basic", 2_000, "month", True),
        ("Pro", 9_900, "month", True),
        ("Team", 29_900, "month", True),
        ("Enterprise", None, "year", False),
    ]
    assert [p["limits"] for p in plans] == [
        {"machines": 1, "precedents": 5_000},
        {"machines": 1, "precedents": 5_000},  # Basic: no licence key, a self-hosted node runs as Free's
        {"machines": 3, "precedents": 50_000},
        {"machines": 10, "precedents": 500_000},
        {"machines": None, "precedents": None},
    ]
    assert [p["features"] for p in plans] == [
        FEATURES_OFF,
        FEATURES_OFF,
        FEATURES_OFF | {"sync": True},
        FEATURES_OFF | {"sync": True},
        {"sync": True, "ha": True, "offline": True, "sso": True},
    ]
    assert all(p["markup_hidden"] is True and "markup_pct" not in p for p in plans)
    assert all(p["built"] == FEATURES_OFF | {"offline": True} for p in plans)  # only offline licences work today
    assert [p["hosting"] for p in plans] == [False, False, True, True, True]  # Free and Basic: self-hosted only
    keys = {"name", "version", "price_cents", "interval", "self_serve", "limits", "features", "built", "markup_hidden"}
    assert keys | {"hosting", "cloud"} == set(plans[0]) and all(p["cloud"] is None for p in plans)  # Ada Cloud is off


async def test_checkout_makes_the_customer_once_and_sells_the_newest_flat_price(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    res = await client.post("/v1/billing/checkout", json={"plan": "team"}, headers=ada.headers)
    assert res.status_code == 200 and res.json() == {"url": "https://checkout.stripe.test/cs_1"}
    (_, path, customer), (_, _, session) = stripe.calls
    assert path == "/customers" and customer["email"] == ada.email and customer["metadata[org_id]"] == str(ada.org_id)
    assert session["mode"] == "subscription" and session["line_items[0][price]"] == "price_test_team"
    assert (session["line_items[0][quantity]"], session["client_reference_id"]) == ("1", str(ada.org_id))
    assert session["line_items[1][price]"] == "price_test_hosting" and "line_items[1][quantity]" not in session
    assert session["success_url"] == "http://localhost:8080/billing/done"
    customer = (await org_row(engine, ada.org_id)).stripe_customer_id
    assert customer.startswith("cus_")
    await client.post("/v1/billing/checkout", json={"plan": "Pro"}, headers=ada.headers)
    assert [c[1] for c in stripe.calls] == ["/customers", "/checkout/sessions", "/checkout/sessions"]
    assert stripe.calls[-1][2]["customer"] == customer


async def test_checkout_refuses_what_it_cannot_sell(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    for body, reason in (
        ({"plan": "Free"}, "not_sold"),
        ({"plan": "Enterprise"}, "not_self_serve"),
        ({"plan": "Gold"}, None),
        ({"plan": ""}, None),
    ):
        res = await client.post("/v1/billing/checkout", json=body, headers=ada.headers)
        assert (res.status_code, res.json()["error"]["code"]) == (422, "E_INVALID"), body
        assert res.json()["error"].get("reason") == reason, body
    enterprise = await client.post("/v1/billing/checkout", json={"plan": "Enterprise"}, headers=ada.headers)
    assert "sales@glyphh.ai" in enterprise.json()["error"]["message"]
    await subscribed(engine, ada.org_id, "sub_solo", "cus_solo")
    res = await client.post("/v1/billing/checkout", json={"plan": "Pro"}, headers=ada.headers)
    assert res.status_code == 409 and res.json()["error"]["reason"] == "subscribed"


async def test_checkout_needs_the_hosting_price(engine: AsyncEngine) -> None:
    from glyphh_server.app import create_app
    from tests.conftest import SETTINGS, _client
    from tests.fakes import fake_http

    ada = await person(engine)
    unpriced = SETTINGS.model_copy(update={"stripe_price_hosting": None})
    async for client in _client(create_app(unpriced, http=fake_http())):
        res = await client.post("/v1/billing/checkout", json={"plan": "Pro"}, headers=ada.headers)
        assert (res.status_code, res.json()["error"]["reason"]) == (503, "billing_off")


async def test_billing_is_the_admins(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    for path, body in (
        ("/v1/billing/checkout", {"plan": "Team"}),
        ("/v1/billing/plan", {"plan": "Pro"}),
        ("/v1/billing/portal", None),
    ):
        res = await client.post(path, json=body, headers=bob.headers)
        assert res.status_code == 403, path


async def test_the_portal_needs_a_customer(client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine)
    none = await client.post("/v1/billing/portal", headers=ada.headers)
    assert none.status_code == 409 and none.json()["error"]["reason"] == "no_billing"
    await subscribed(engine, ada.org_id, "sub_portal", "cus_portal")
    res = await client.post("/v1/billing/portal", headers=ada.headers)
    assert res.json() == {"url": "https://billing.stripe.test/p_1"}
    assert stripe.calls[-1][2] == {"customer": "cus_portal", "return_url": "http://localhost:8080/billing/done"}
    done = await client.get("/billing/done")
    assert done.status_code == 302 and done.headers["location"] == "http://localhost:3000/billing?done=1"


async def test_changing_plan_moves_to_the_newest_version_prorated(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    stripe.sub("sub_up", "cus_up", "price_test_pro", 1)
    await subscribed(engine, ada.org_id, "sub_up", "cus_up")
    res = await client.post("/v1/billing/plan", json={"plan": "Team"}, headers=ada.headers)
    assert res.status_code == 200 and (res.json()["plan"]["name"], res.json()["billing_status"]) == ("Team", "active")
    change = stripe.calls[-1]
    assert change[1] == "/subscriptions/sub_up" and change[2]["items[0][price]"] == "price_test_team"
    assert change[2]["items[0][id]"] == "si_sub_up" and change[2]["items[0][quantity]"] == "1"
    assert change[2]["proration_behavior"] == "create_prorations"
    calls = len(stripe.calls)
    same = await client.post("/v1/billing/plan", json={"plan": "Team"}, headers=ada.headers)
    assert same.json()["plan"]["name"] == "Team" and len(stripe.calls) == calls


async def test_a_subscription_without_a_plan_item_gets_one(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    stripe.sub("sub_bare", "cus_bare", "price_unknown", 1)
    await subscribed(engine, ada.org_id, "sub_bare", "cus_bare")
    res = await client.post("/v1/billing/plan", json={"plan": "Team"}, headers=ada.headers)
    assert res.json()["plan"]["name"] == "Team"
    assert "items[0][id]" not in stripe.calls[-1][2] and stripe.calls[-1][2]["items[0][price]"] == "price_test_team"


async def test_changing_plan_needs_a_subscription_and_self_serve_plans(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team")
    unsubscribed = await client.post("/v1/billing/plan", json={"plan": "Pro"}, headers=ada.headers)
    assert unsubscribed.status_code == 409 and unsubscribed.json()["error"]["reason"] == "not_subscribed"
    stripe.sub("sub_team", "cus_team", "price_test_team", 1)
    await subscribed(engine, ada.org_id, "sub_team", "cus_team")
    enterprise = await client.post("/v1/billing/plan", json={"plan": "Enterprise"}, headers=ada.headers)
    assert enterprise.status_code == 422 and enterprise.json()["error"]["reason"] == "not_self_serve"
    contract = await person(engine, "Enterprise")
    await subscribed(engine, contract.org_id, "sub_deal", "cus_deal")
    res = await client.post("/v1/billing/plan", json={"plan": "Pro"}, headers=contract.headers)
    assert res.status_code == 409 and res.json()["error"]["reason"] == "contract"


async def test_down_to_free_cancels_now_once_no_machine_is_left(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    stripe.sub("sub_down", "cus_down", "price_test_team", 1)
    await subscribed(engine, ada.org_id, "sub_down", "cus_down")
    await hosted_runtime(engine, ada)
    machine = await hosted_runtime(engine, bob)  # two, the org's together: Free allows one
    held = await client.post("/v1/billing/plan", json={"plan": "Free"}, headers=ada.headers)
    assert held.status_code == 409 and held.json()["error"]["reason"] == "machines"
    assert held.json()["error"]["message"] == "Delete your hosted machines first. Free allows 1 hosted machine."
    async with engine.begin() as conn:
        await conn.execute(delete(Rrotor).where(Rrotor.id == machine.id))
    res = await client.post("/v1/billing/plan", json={"plan": "Free"}, headers=ada.headers)
    assert res.status_code == 200 and (res.json()["plan"]["name"], res.json()["billing_status"]) == ("Free", "canceled")
    assert stripe.calls[-1] == ("DELETE", "/subscriptions/sub_down", {"invoice_now": "true", "prorate": "true"})
    assert (await org_row(engine, ada.org_id)).stripe_subscription_id is None


async def test_stripe_down_or_billing_off_is_unavailable(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    stripe.fail = True
    res = await client.post("/v1/billing/checkout", json={"plan": "Pro"}, headers=ada.headers)
    assert res.status_code == 503 and res.json()["error"]["reason"] == "stripe"
