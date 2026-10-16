"""The add-on catalog for the org's plan, Checkout with add-ons, and the license carrying the add-ons an org has."""

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Addon
from tests.addons import CONFETTI, confetti
from tests.db.helpers import member, person, with_addon
from tests.fakes import FakeStripe


async def test_the_catalog_shows_each_addon_its_price_and_whether_the_plan_may_have_it(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    free = await person(engine)
    listed = (await client.get("/v1/addons", headers=free.headers)).json()
    assert [(a["mod"], a["price_cents"], a["allowed"], a["limits"], a["added"]) for a in listed] == [
        ("programs", 400, False, None, False),
        ("gateway", 400, False, None, False),
        ("ada", 400, False, None, False),
    ]
    assert listed[0] | {"description": ""} == {
        "mod": "programs",
        "name": "Programs",
        "description": "",
        "version": 1,
        "price_cents": 400,
        "per_seat": True,
        "monthly_cents": 400,
        "plans": ["Pro", "Team"],
        "free": False,
        "allowed": False,
        "limits": None,
        "added": False,
        "quantity": None,
    }
    assert (await client.get("/v1/addons")).status_code == 401


async def test_the_catalog_for_a_team_shows_team_limits_seat_prices_and_what_it_has(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team", seats=3)
    await with_addon(engine, ada.org_id, "programs", quantity=3)
    bob = await member(engine, ada.org_id)
    listed = {a["mod"]: a for a in (await client.get("/v1/addons", headers=bob.headers)).json()}
    assert (listed["programs"]["added"], listed["programs"]["quantity"]) == (True, 3)
    assert listed["programs"]["limits"] == {"programs": None, "runs_per_day": None}
    assert (listed["programs"]["monthly_cents"], listed["gateway"]["monthly_cents"]) == (1200, 1200)
    assert listed["gateway"]["limits"] == {"keys": None, "models": None} and not listed["gateway"]["added"]


async def test_the_license_carries_each_addon_with_its_limits_on_the_orgs_plan(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team", seats=2)
    await with_addon(engine, ada.org_id, "gateway", quantity=2)
    mods = (await client.get("/v1/license", headers=ada.headers)).json()["payload"]["mods"]
    assert mods == {
        "gateway": {"limits": {"keys": None, "models": None}},
    }


async def test_checkout_sells_the_plan_and_each_addon_as_its_own_line(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team", seats=3)
    async with confetti(engine):
        body = {"plan": "Team", "seats": 3, "addons": ["gateway", "Confetti"]}
        res = await client.post("/v1/billing/checkout", json=body, headers=ada.headers)
    assert res.status_code == 200
    session = stripe.calls[-1][2]
    assert [(session[f"line_items[{i}][price]"], session[f"line_items[{i}][quantity]"]) for i in range(3)] == [
        ("price_test_team", "3"),
        ("price_test_gateway", "3"),
        ("price_test_confetti", "1"),
    ]


async def test_a_free_org_checks_out_only_addons_allowed_on_free(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    async with confetti(engine):
        res = await client.post(
            "/v1/billing/checkout", json={"plan": "Free", "seats": 1, "addons": ["confetti"]}, headers=ada.headers
        )
        assert res.status_code == 200
        session = stripe.calls[-1][2]
        assert (session["line_items[0][price]"], "line_items[1][price]" in session) == ("price_test_confetti", False)
        for addons, status, reason in (
            (["gateway"], 409, "not_on_plan"),
            (["confetti", "confetti"], 422, "duplicate_addon"),
            (["rpa"], 422, "no_addon"),
        ):
            body = {"plan": "Free", "seats": 1, "addons": addons}
            res = await client.post("/v1/billing/checkout", json=body, headers=ada.headers)
            assert (res.status_code, res.json()["error"].get("reason")) == (status, reason), addons
    pro = await client.post(
        "/v1/billing/checkout", json={"plan": "Pro", "seats": 1, "addons": ["confetti"]}, headers=ada.headers
    )
    assert pro.json()["error"]["reason"] == "no_addon"


async def test_an_addon_off_sale_or_without_a_stripe_price_is_not_sold(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team")
    async with engine.begin() as conn:
        await conn.execute(update(Addon).where(Addon.mod == "ada").values(active=False))
    try:
        res = await client.post(
            "/v1/billing/checkout", json={"plan": "Pro", "seats": 1, "addons": ["ada"]}, headers=ada.headers
        )
        assert res.status_code == 422 and res.json()["error"]["reason"] == "no_addon"
        assert "ada" not in [a["mod"] for a in (await client.get("/v1/addons", headers=ada.headers)).json()]
    finally:
        async with engine.begin() as conn:
            await conn.execute(update(Addon).where(Addon.mod == "ada").values(active=True))
    async with confetti(engine):
        async with engine.begin() as conn:
            await conn.execute(update(Addon).where(Addon.mod == CONFETTI).values(stripe_price_id=None))
        body = {"plan": "Team", "seats": 1, "addons": [CONFETTI]}
        res = await client.post("/v1/billing/checkout", json=body, headers=ada.headers)
        assert res.json()["error"]["reason"] == "no_addon"
