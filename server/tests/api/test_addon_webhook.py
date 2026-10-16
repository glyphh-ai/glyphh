"""Stripe's webhook keeps the org's add-ons true to its subscription's items: read fresh, so replays and events out of
order change nothing; an ended subscription removes them all; an item of no price Glyphh sells is left alone."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.addons import org_addons
from tests.api.test_stripe_webhook import _event, _plan, _send
from tests.db.helpers import person
from tests.fakes import FakeStripe


async def test_a_finished_checkout_records_each_addon_and_a_replay_changes_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    sub = f"sub_{ada.org_id.hex}"
    stripe.sub(sub, f"cus_{ada.org_id.hex}", "price_test_team", 3)
    gateway = stripe.add_item(sub, "price_test_gateway", 3)
    programs = stripe.add_item(sub, "price_test_programs", 3)
    obj = {"mode": "subscription", "client_reference_id": str(ada.org_id), "customer": None, "subscription": sub}
    for _ in range(2):
        assert (await _send(client, _event("checkout.session.completed", obj))).status_code == 204
        assert await _plan(engine, ada.org_id) == ("Team", 3, "active", sub)
        assert await org_addons(engine, ada.org_id) == {
            "gateway": ("active", gateway["id"], 3),
            "programs": ("active", programs["id"], 3),
        }
    mods = (await client.get("/v1/license", headers=ada.headers)).json()["payload"]["mods"]
    assert list(mods) == ["gateway", "programs", "workspaces"]


async def test_an_addon_gone_from_the_subscription_is_removed_even_when_older_events_arrive_after(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    sub, customer = f"sub_{ada.org_id.hex}", f"cus_{ada.org_id.hex}"
    stripe.sub(sub, customer, "price_test_pro", 1)
    gateway = stripe.add_item(sub, "price_test_gateway", 1)
    obj = {"id": sub, "customer": customer, "metadata": {"org_id": str(ada.org_id)}}
    await _send(client, _event("customer.subscription.created", obj))
    stripe.subs[sub]["items"]["data"].remove(gateway)
    await _send(client, _event("customer.subscription.updated", obj))
    assert await org_addons(engine, ada.org_id) == {"gateway": ("removed", None, 1)}
    late = obj | {"items": {"data": [gateway]}}
    await _send(client, _event("customer.subscription.created", late))
    assert await org_addons(engine, ada.org_id) == {"gateway": ("removed", None, 1)}
    stripe.add_item(sub, "price_test_gateway", 1)
    await _send(client, _event("customer.subscription.updated", obj))
    assert await org_addons(engine, ada.org_id) == {"gateway": ("active", f"si_{sub}_price_test_gateway", 1)}


async def test_an_ended_subscription_removes_every_addon_and_unknown_prices_are_left_alone(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    sub, customer = f"sub_{ada.org_id.hex}", f"cus_{ada.org_id.hex}"
    stripe.sub(sub, customer, "price_test_pro", 1)
    stripe.add_item(sub, "price_from_elsewhere", 7)
    stripe.add_item(sub, "price_test_ada", 1)
    obj = {"id": sub, "customer": customer, "metadata": {"org_id": str(ada.org_id)}}
    await _send(client, _event("customer.subscription.updated", obj))
    assert await _plan(engine, ada.org_id) == ("Pro", 1, "active", sub)
    assert await org_addons(engine, ada.org_id) == {"ada": ("active", f"si_{sub}_price_test_ada", 1)}
    stripe.subs[sub]["status"] = "canceled"
    for _ in range(2):
        await _send(client, _event("customer.subscription.deleted", obj))
        assert await _plan(engine, ada.org_id) == ("Free", 1, "canceled", None)
        assert await org_addons(engine, ada.org_id) == {"ada": ("removed", None, 1)}
