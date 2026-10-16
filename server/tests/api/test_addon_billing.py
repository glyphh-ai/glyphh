"""Adding and removing add-ons on a subscription, prorated and previewed first; the refusals; per-seat quantities
following the seats; changing plan with add-ons. All against the fake Stripe."""

import time

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.addons import CONFETTI, confetti, on_stripe, org_addons
from tests.db.helpers import member, person
from tests.fakes import FakeStripe


async def test_previewing_changes_nothing_and_adding_then_removing_is_prorated(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada, sub = await on_stripe(engine, stripe, "Pro")
    seen = await client.post("/v1/billing/addons/preview", json={"mod": "ada", "action": "add"}, headers=ada.headers)
    assert seen.status_code == 200
    preview = seen.json()
    assert preview | {"proration_date": 0} == {
        "mod": "ada",
        "action": "add",
        "prorated_cents": 200,
        "currency": "usd",
        "monthly_cents": 400,
        "proration_date": 0,
    }
    assert abs(preview["proration_date"] - time.time()) < 60
    asked = stripe.calls[-1]
    assert asked[1] == "/invoices/create_preview" and asked[2]["subscription"] == sub
    assert asked[2]["subscription_details[items][0][price]"] == "price_test_ada"
    assert asked[2]["subscription_details[proration_behavior]"] == "create_prorations"
    assert len(stripe.subs[sub]["items"]["data"]) == 1 and await org_addons(engine, ada.org_id) == {}
    body = {"mod": "ada", "proration_date": preview["proration_date"]}
    added = await client.post("/v1/billing/addons", json=body, headers=ada.headers)
    added_ada = next(a for a in added.json() if a["mod"] == "ada")
    assert (added.status_code, added_ada["added"], added_ada["quantity"]) == (200, True, 1)
    change = stripe.calls[-1][2]
    assert (change["items[0][price]"], change["items[0][quantity]"]) == ("price_test_ada", "1")
    assert change["proration_date"] == str(preview["proration_date"])
    item = stripe.subs[sub]["items"]["data"][1]["id"]
    assert await org_addons(engine, ada.org_id) == {"ada": ("active", item, 1)}
    lic = (await client.get("/v1/license", headers=ada.headers)).json()["payload"]["mods"]
    assert list(lic) == ["ada"]
    credit = await client.post(
        "/v1/billing/addons/preview", json={"mod": "ada", "action": "remove"}, headers=ada.headers
    )
    assert credit.json()["prorated_cents"] == -200
    gone = await client.delete("/v1/billing/addons/ada", headers=ada.headers)
    assert gone.status_code == 200 and not next(a for a in gone.json() if a["mod"] == "ada")["added"]
    assert (stripe.calls[-1][2]["items[0][id]"], stripe.calls[-1][2]["items[0][deleted]"]) == (item, "true")
    assert "proration_date" not in stripe.calls[-1][2]
    assert await org_addons(engine, ada.org_id) == {"ada": ("removed", None, 1)}
    assert list((await client.get("/v1/license", headers=ada.headers)).json()["payload"]["mods"]) == []


async def test_adding_and_removing_refuse_with_stable_codes(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    free = await person(engine)
    res = await client.post("/v1/billing/addons", json={"mod": "ada"}, headers=free.headers)
    assert (res.status_code, res.json()["error"]["reason"]) == (409, "not_subscribed")
    ada, _ = await on_stripe(engine, stripe, "Pro")
    bob = await member(engine, ada.org_id)
    for method, path, body in (
        ("POST", "/v1/billing/addons/preview", {"mod": "ada", "action": "add"}),
        ("POST", "/v1/billing/addons", {"mod": "ada"}),
        ("DELETE", "/v1/billing/addons/ada", None),
    ):
        res = await client.request(method, path, json=body, headers=bob.headers)
        assert res.json()["error"]["code"] == "E_FORBIDDEN", path
    await client.post("/v1/billing/addons", json={"mod": "ada"}, headers=ada.headers)
    async with confetti(engine):
        for method, path, body, status, reason in (
            ("POST", "/v1/billing/addons", {"mod": "Ada"}, 409, "already_added"),
            ("POST", "/v1/billing/addons", {"mod": CONFETTI}, 409, "not_on_plan"),
            ("POST", "/v1/billing/addons", {"mod": "nothing"}, 422, "no_addon"),
            ("DELETE", f"/v1/billing/addons/{CONFETTI}", None, 404, "not_added"),
            ("POST", "/v1/billing/addons/preview", {"mod": CONFETTI, "action": "remove"}, 404, "not_added"),
        ):
            res = await client.request(method, path, json=body, headers=ada.headers)
            assert (res.status_code, res.json()["error"]["reason"]) == (status, reason), (path, body)
    bad = await client.post("/v1/billing/addons/preview", json={"mod": "ada", "action": "keep"}, headers=ada.headers)
    assert bad.status_code == 422


async def test_per_seat_addons_follow_the_seats_and_flat_ones_stay_at_one(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    async with confetti(engine):
        ada, sub = await on_stripe(engine, stripe, "Team", seats=2)
        for mod in ("ada", CONFETTI):
            assert (await client.post("/v1/billing/addons", json={"mod": mod}, headers=ada.headers)).status_code == 200
        assert {m: q for m, (_, _, q) in (await org_addons(engine, ada.org_id)).items()} == {"ada": 2, CONFETTI: 1}
        res = await client.post("/v1/billing/seats", json={"seats": 4}, headers=ada.headers)
        assert res.status_code == 200 and res.json()["seats"] == 4
        change = stripe.calls[-1][2]
        items = stripe.subs[sub]["items"]["data"]
        assert change == {
            "items[0][id]": items[0]["id"],
            "items[0][quantity]": "4",
            "items[1][id]": items[1]["id"],
            "items[1][quantity]": "4",
            "proration_behavior": "create_prorations",
        }
        assert {m: q for m, (_, _, q) in (await org_addons(engine, ada.org_id)).items()} == {"ada": 4, CONFETTI: 1}
        lic = (await client.get("/v1/license", headers=ada.headers)).json()["payload"]["mods"]
        assert lic[CONFETTI] == {"limits": {"bursts": None}}


async def test_changing_plan_keeps_the_seats_on_the_new_price(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada, sub = await on_stripe(engine, stripe, "Team", seats=1)
    await client.post("/v1/billing/addons", json={"mod": "ada"}, headers=ada.headers)
    res = await client.post("/v1/billing/plan", json={"plan": "Pro"}, headers=ada.headers)
    assert res.status_code == 200 and res.json()["plan"]["name"] == "Pro"
    change = stripe.calls[-1][2]
    assert (change["items[0][price]"], change["items[0][quantity]"], change["items[0][id]"]) == (
        "price_test_pro",
        "1",
        f"si_{sub}",
    )
    lic = (await client.get("/v1/license", headers=ada.headers)).json()["payload"]["mods"]
    assert lic["ada"] == {"limits": {"models": 3, "precedents": 10000}}


async def test_a_free_org_with_only_addons_keeps_its_last_one_until_it_cancels_or_takes_a_plan(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    async with confetti(engine):
        ada, sub = await on_stripe(engine, stripe, "Free")
        assert (await client.post("/v1/billing/addons", json={"mod": CONFETTI}, headers=ada.headers)).status_code == 200
        no = await client.post("/v1/billing/addons", json={"mod": "ada"}, headers=ada.headers)
        assert no.json()["error"]["reason"] == "not_on_plan"
        last = await client.delete(f"/v1/billing/addons/{CONFETTI}", headers=ada.headers)
        assert (last.status_code, last.json()["error"]["reason"]) == (409, "last_item")
        seats = await client.post("/v1/billing/seats", json={"seats": 1}, headers=ada.headers)
        assert seats.status_code == 200 and "items[0][id]" not in stripe.calls[-1][2]
        moved = await client.post("/v1/billing/plan", json={"plan": "Pro"}, headers=ada.headers)
        assert (moved.status_code, moved.json()["error"]["reason"]) == (409, "not_on_plan")
        res = await client.post("/v1/billing/plan", json={"plan": "Team"}, headers=ada.headers)
        assert res.status_code == 200 and res.json()["plan"]["name"] == "Team"
        change = stripe.calls[-1][2]
        assert (change["items[0][price]"], change["items[0][quantity]"], "items[0][id]" in change) == (
            "price_test_team",
            "1",
            False,
        )
        assert [i["price"]["id"] for i in stripe.subs[sub]["items"]["data"]] == [
            "price_test_confetti",
            "price_test_team",
        ]
        gone = await client.delete(f"/v1/billing/addons/{CONFETTI}", headers=ada.headers)
        assert gone.status_code == 200
