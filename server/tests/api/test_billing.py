"""Plans and billing: Checkout, plan changes, Stripe's portal, all against a fake Stripe."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.helpers import member, org_row, person, subscribed
from tests.fakes import FakeStripe


async def test_billing_shows_the_plan_to_every_member(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    bob = await member(engine, ada.org_id)
    billing = (await client.get("/v1/billing", headers=ada.headers)).json()
    assert (billing["plan"]["name"], billing["billing_status"], billing["renews_at"]) == ("Pro", "none", None)
    assert billing["cloud"] is None and billing["plan_until"] is None  # Ada Cloud off, no Enterprise grant
    assert set(billing) == {"plan", "cloud", "tokens", "balance", "billing_status", "renews_at", "plan_until"}
    me = (await client.get("/v1/me", headers=bob.headers)).json()
    assert me["plan"] == billing["plan"]
    assert (await client.get("/v1/billing")).status_code == 401


async def test_the_plans_are_free_basic_pro_team_and_enterprise(
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
    assert [p["features"] for p in plans] == [{"sso": False}] * 4 + [{"sso": True}]  # single sign-on: Enterprise's
    assert all(p["built"] == {"sso": True} for p in plans)  # single sign-on works today
    keys = {"name", "version", "price_cents", "interval", "self_serve", "features", "built"}
    assert keys | {"cloud", "llm_tokens"} == set(plans[0])
    assert all(p["cloud"] is None for p in plans)  # Ada Cloud off
    # Glyphh-hosted models' tokens a month (docs/specs/tokens.md): a plan's fact, shown whether they are on or not
    assert [p["llm_tokens"] for p in plans] == [250_000, 5_000_000, 25_000_000, 100_000_000, None]


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
    assert "line_items[1][price]" not in session  # nothing metered while Ada Cloud is off
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


async def test_down_to_free_cancels_now(client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine, "Team")
    stripe.sub("sub_down", "cus_down", "price_test_team", 1)
    await subscribed(engine, ada.org_id, "sub_down", "cus_down")
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
