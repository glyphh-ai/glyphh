"""Hosted machines held past the plan: an org that lands on a plan allowing fewer machines than one of its people
holds has every such person's machines stopped and none started (E_LIMIT machines) until a plan allows them; they
may still be deleted. A plan change that would leave machines past it is refused."""

import json
import time
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.errors import LimitReached
from glyphh_server.models import Org, Rrotor
from glyphh_server.ops.billing.signature import sign
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.held import hold
from glyphh_server.ops.idle import waker
from glyphh_server.ops.plans import newest_version
from tests.api.test_hosted import FLY_SETTINGS
from tests.conftest import WEBHOOK_SECRET, _client
from tests.db.helpers import Person, person, subscribed
from tests.fakes import FakeFly, FakeStripe, fake_http
from tests.link import hosted_runtime, runtime_row


async def _machine(engine: AsyncEngine, fly: FakeFly, who: Person, name: str, state: str = "online") -> Any:
    rt = await hosted_runtime(engine, who, name)
    machine = f"m_{rt.id.hex[:12]}"
    fly.machines[machine] = {"id": machine, "state": "started" if state == "online" else "stopped"}
    async with engine.begin() as conn:
        values = {"state": state, "fly_machine_id": machine}
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(**values))
    return rt, machine


async def _on(engine: AsyncEngine, who: Person, plan: str) -> None:
    async with engine.begin() as conn:
        version = await newest_version(conn, plan)
        await conn.execute(update(Org).where(Org.id == who.org_id).values(plan_version_id=version.id))


def _limit(res: httpx.Response) -> dict[str, Any]:
    assert res.status_code == 403, res.text
    error = res.json()["error"]
    assert (error["code"], error["reason"]) == ("E_LIMIT", "machines")
    return error


async def test_machines_past_the_plan_start_never_and_are_deleted_still(engine: AsyncEngine) -> None:
    fly = FakeFly()
    ada = await person(engine, "Pro")
    (a, _), (b, _) = await _machine(engine, fly, ada, "a", "stopped"), await _machine(engine, fly, ada, "b", "stopped")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        assert (await client.post(f"/v1/runtimes/{a.id}/start", headers=ada.headers)).status_code == 200
        await _on(engine, ada, "Free")
        for path in (f"/v1/runtimes/{a.id}/start", f"/v1/runtimes/{b.id}/restart", "/v1/runtime/start"):
            error = _limit(await client.post(path, headers=ada.headers))
            assert (error["used"], error["max"], error["plan"]) == (2, 0, "Pro"), path
        with pytest.raises(LimitReached):
            await waker(engine, Fly(fake_http(fly=fly), FLY_SETTINGS))(a.id)
        assert (await client.delete(f"/v1/runtimes/{b.id}?confirm=b", headers=ada.headers)).status_code == 204
        await _on(engine, ada, "Pro")  # back on a plan that allows it
        assert (await client.post(f"/v1/runtimes/{a.id}/start", headers=ada.headers)).status_code == 200


async def test_hold_stops_every_machine_past_the_plan_that_is_not_stopped(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    fly = FakeFly()
    ada, eve, ok = await person(engine), await person(engine), await person(engine, "Pro")
    (on, on_m), (off, _) = await _machine(engine, fly, ada, "on"), await _machine(engine, fly, ada, "off", "stopped")
    lost, lost_m = await _machine(engine, fly, ada, "lost")
    theirs, theirs_m = await _machine(engine, fly, eve, "theirs")
    fine, fine_m = await _machine(engine, fly, ok, "fine")
    del fly.machines[lost_m]  # Fly lost it: logged, tried again at the next tick
    client = Fly(fake_http(fly=fly), FLY_SETTINGS)
    async with engine.begin() as conn:
        assert await hold(conn, client, ada.org_id) == [on.id]
    assert fly.machines[on_m]["state"] == "stopped" and fly.machines[theirs_m]["state"] == "started"
    assert [(await runtime_row(engine, r.id)).state for r in (on, off, lost)] == ["stopped", "stopped", "online"]
    assert "machine past the plan not stopped" in caplog.text
    async with engine.begin() as conn:
        assert theirs.id in await hold(conn, client)  # every org's: the tick's
        assert await hold(conn, client, ada.org_id) == []
    assert fly.machines[fine_m]["state"] == "started" and fine.id


async def test_a_subscription_ending_stops_the_orgs_machines_at_once(engine: AsyncEngine, stripe: FakeStripe) -> None:
    fly = FakeFly()
    ada = await person(engine, "Team")
    sub, customer = f"sub_{ada.org_id.hex}", f"cus_{ada.org_id.hex}"
    await subscribed(engine, ada.org_id, sub, customer)
    _, machine = await _machine(engine, fly, ada, "research")
    stripe.sub(sub, customer, "price_test_team", 1, "canceled")
    body = json.dumps({"type": "customer.subscription.deleted", "data": {"object": {"id": sub, "customer": customer}}})
    headers = {"stripe-signature": sign(WEBHOOK_SECRET, body.encode(), int(time.time()))}
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(stripe, fly=fly))):
        assert (await client.post("/v1/stripe/webhook", content=body, headers=headers)).status_code == 204
        assert (await client.get("/v1/me", headers=ada.headers)).json()["plan"]["name"] == "Free"
    assert fly.machines[machine]["state"] == "stopped"


async def test_a_plan_with_fewer_machines_than_held_is_refused(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    fly = FakeFly()
    ada = await person(engine, "Team")
    stripe.sub("sub_four", "cus_four", "price_test_team", 1)
    await subscribed(engine, ada.org_id, "sub_four", "cus_four")
    for name in ("a", "b", "c", "d"):
        await _machine(engine, fly, ada, name)
    res = await client.post("/v1/billing/plan", json={"plan": "Pro"}, headers=ada.headers)
    error = res.json()["error"]
    assert (res.status_code, error["code"], error["reason"], error["held"], error["max"]) == (
        409,
        "E_CONFLICT",
        "machines",
        4,
        3,
    )
    assert error["message"] == "Delete your hosted machines first. Pro allows 3 for each person."
