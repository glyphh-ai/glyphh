"""Plans and billing: Checkout, plan and seat changes, Stripe's portal, all against a fake Stripe."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.helpers import member, org_row, person, subscribed
from tests.fakes import FakeStripe


async def test_the_plans_are_free_pro_and_team(client: httpx.AsyncClient) -> None:
    plans = (await client.get("/v1/plans")).json()
    assert [(p["name"], p["seat_price_cents"]) for p in plans] == [("Free", 0), ("Pro", 800), ("Team", 1600)]
    assert [p["limits"] for p in plans] == [
        {"members": 1, "installs": 1},
        {"members": 1, "installs": 5},
        {"members": None, "installs": 10},
    ]
    assert [p["mods"] for p in plans] == [
        {
            "drips": {"limits": {"custom_drips": 3, "fullscreen": 0}},
            "programs": {"limits": {"programs": 3, "runs_per_day": 50}},
            "workspaces": {"limits": {"favorites": 5, "stream": 0, "workspaces": 2}},
        },
        {
            "drips": {"limits": {"custom_drips": None, "fullscreen": 1}},
            "programs": {"limits": {"programs": 25, "runs_per_day": 1000}},
            "workspaces": {"limits": {"favorites": None, "stream": 1, "workspaces": 10}},
        },
        {
            "drips": {"limits": {"custom_drips": None, "fullscreen": 1}},
            "programs": {"limits": {"programs": None, "runs_per_day": None}},
            "workspaces": {"limits": {"favorites": None, "stream": 1, "workspaces": None}},
        },
    ]


async def test_checkout_makes_the_customer_once_and_sells_the_newest_price_per_seat(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    res = await client.post("/v1/billing/checkout", json={"plan": "team", "seats": 4}, headers=ada.headers)
    assert res.status_code == 200 and res.json() == {"url": "https://checkout.stripe.test/cs_1"}
    (_, path, customer), (_, _, session) = stripe.calls
    assert path == "/customers" and customer["email"] == ada.email and customer["metadata[org_id]"] == str(ada.org_id)
    assert session["mode"] == "subscription" and session["line_items[0][price]"] == "price_test_team"
    assert (session["line_items[0][quantity]"], session["client_reference_id"]) == ("4", str(ada.org_id))
    assert session["success_url"] == "http://localhost:8080/billing/done"
    assert (await org_row(engine, ada.org_id)).stripe_customer_id == "cus_1"
    await client.post("/v1/billing/checkout", json={"plan": "Pro", "seats": 1}, headers=ada.headers)
    assert [c[1] for c in stripe.calls] == ["/customers", "/checkout/sessions", "/checkout/sessions"]
    assert stripe.calls[-1][2]["customer"] == "cus_1"


async def test_checkout_refuses_what_it_cannot_sell(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team", seats=2)
    await member(engine, ada.org_id)
    for body, status, code in (
        ({"plan": "Free", "seats": 1}, 422, "E_INVALID"),
        ({"plan": "Gold", "seats": 1}, 422, "E_INVALID"),
        ({"plan": "Team", "seats": 1}, 409, "E_CONFLICT"),
        ({"plan": "Pro", "seats": 2}, 422, "E_INVALID"),
        ({"plan": "Team", "seats": 0}, 422, "E_INVALID"),
    ):
        res = await client.post("/v1/billing/checkout", json=body, headers=ada.headers)
        assert (res.status_code, res.json()["error"]["code"]) == (status, code), body
    solo = await person(engine)
    res = await client.post("/v1/billing/checkout", json={"plan": "Pro", "seats": 2}, headers=solo.headers)
    assert res.status_code == 422 and "room for 1 members" in res.json()["error"]["message"]
    await subscribed(engine, solo.org_id, "sub_solo", "cus_solo")
    res = await client.post("/v1/billing/checkout", json={"plan": "Pro", "seats": 1}, headers=solo.headers)
    assert res.status_code == 409 and res.json()["error"]["reason"] == "subscribed"


async def test_billing_is_the_admins(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team", seats=2)
    bob = await member(engine, ada.org_id)
    for path, body in (
        ("/v1/billing/checkout", {"plan": "Team", "seats": 2}),
        ("/v1/billing/plan", {"plan": "Pro"}),
        ("/v1/billing/seats", {"seats": 3}),
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
    assert done.status_code == 200 and "Go back to Claude" in done.text


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
    assert change[2]["items[0][id]"] == "si_sub_up" and change[2]["proration_behavior"] == "create_prorations"
    calls = len(stripe.calls)
    same = await client.post("/v1/billing/plan", json={"plan": "Team"}, headers=ada.headers)
    assert same.json()["plan"]["name"] == "Team" and len(stripe.calls) == calls


async def test_changing_plan_needs_a_subscription_a_paid_plan_and_room(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team", seats=2)
    unsubscribed = await client.post("/v1/billing/plan", json={"plan": "Pro"}, headers=ada.headers)
    assert unsubscribed.status_code == 409 and unsubscribed.json()["error"]["reason"] == "not_subscribed"
    stripe.sub("sub_team", "cus_team", "price_test_team", 2)
    await subscribed(engine, ada.org_id, "sub_team", "cus_team")
    free = await client.post("/v1/billing/plan", json={"plan": "Free"}, headers=ada.headers)
    assert free.status_code == 422 and "billing portal" in free.json()["error"]["message"]
    crowded = await client.post("/v1/billing/plan", json={"plan": "Pro"}, headers=ada.headers)
    assert crowded.status_code == 422 and "room for 1 members" in crowded.json()["error"]["message"]


async def test_seats_change_prorated_and_never_below_those_taken(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team", seats=3)
    await member(engine, ada.org_id)
    stripe.sub("sub_seats", "cus_seats", "price_test_team", 3)
    await subscribed(engine, ada.org_id, "sub_seats", "cus_seats")
    res = await client.post("/v1/billing/seats", json={"seats": 5}, headers=ada.headers)
    assert res.status_code == 200 and res.json()["seats"] == 5
    assert stripe.calls[-1][2]["items[0][quantity]"] == "5"
    low = await client.post("/v1/billing/seats", json={"seats": 1}, headers=ada.headers)
    assert low.status_code == 409 and low.json()["error"]["used"] == 2


async def test_stripe_down_or_billing_off_is_unavailable(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    stripe.fail = True
    res = await client.post("/v1/billing/checkout", json={"plan": "Pro", "seats": 1}, headers=ada.headers)
    assert res.status_code == 503 and res.json()["error"]["reason"] == "stripe"
