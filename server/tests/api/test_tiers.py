"""Glyphh's managed cloud switched off (GLYPHH_HOSTING, off by default): no hosted machine is made, started or
restarted, from the API or from Claude, the plans keep their runtime nodes, the tick meters nothing, Checkout sells no
hosting, /v1/rates says so and an Enterprise grant needs no markup. Machines made before can still be stopped and
deleted. The rest of the suite runs with it on."""

from datetime import timedelta
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.models import Rrotor
from glyphh_server.ops import enterprise, tend
from glyphh_server.ops.hosted import HOSTING_OFF as HOSTING_OFF_SAID
from glyphh_server.ops.link.hub import Hub
from tests.api.test_hosted import FLY_SETTINGS
from tests.api.test_mcp_tools import _refused
from tests.conftest import _client
from tests.connector import granted, rpc, tool
from tests.db.helpers import org_row, person
from tests.fakes import FakeFly, FakeStripe, fake_http
from tests.link import hosted_runtime

HOSTING_OFF: Settings = FLY_SETTINGS.model_copy(update={"hosting": False})  # Fly set up, the managed cloud off
OFF_SAID: str = "Glyphh's managed cloud is off: run rrotor yourself and register it with register_self_runtime."


def test_hosting_is_off_unless_set_on() -> None:
    bare = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (bare.hosting, bare.hosting_on) == (False, False)
    on = Settings(_env_file=None, hosting="on")  # type: ignore[call-arg]
    assert (on.hosting, on.hosting_on) == (True, False)  # on, but no Fly: nothing is made
    assert Settings(_env_file=None, hosting="off").hosting is False  # type: ignore[call-arg]
    assert FLY_SETTINGS.hosting_on and not HOSTING_OFF.hosting_on


def _off(res: httpx.Response) -> None:
    assert res.status_code == 503, res.text
    error = res.json()["error"]
    assert (error["code"], error["reason"]) == ("E_UNAVAILABLE", "hosting_off")
    assert error["message"] == HOSTING_OFF_SAID


async def test_with_hosting_off_no_machine_is_made_or_started_and_none_is_shown(engine: AsyncEngine) -> None:
    fly = FakeFly()
    ada = await person(engine, "Pro")
    rt = await hosted_runtime(engine, ada, "older")
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(fly_machine_id="m_old", fly_volume_id="v"))
    fly.machines["m_old"] = {"id": "m_old", "state": "started"}
    async for client in _client(create_app(HOSTING_OFF, http=fake_http(fly=fly))):
        plans = (await client.get("/v1/plans")).json()
        assert [p["limits"]["machines"] for p in plans] == [1, 1, 3, 10, None]  # runtime nodes, hosting or not
        _off(await client.get("/v1/rates"))
        _off(await client.post("/v1/runtimes", json={"name": "research", "size": "small"}, headers=ada.headers))
        _off(await client.post("/v1/runtime/start", headers=ada.headers))
        _off(await client.post(f"/v1/runtimes/{rt.id}/start", headers=ada.headers))
        _off(await client.post(f"/v1/runtimes/{rt.id}/restart", headers=ada.headers))
        assert fly.calls == []  # nothing made, no doorman
        stopped = await client.post(f"/v1/runtimes/{rt.id}/stop", headers=ada.headers)
        assert stopped.status_code == 200, stopped.text  # one made before can still be stopped and deleted
        gone = await client.delete(f"/v1/runtimes/{rt.id}", params={"confirm": "older"}, headers=ada.headers)
        assert gone.status_code == 204, gone.text


async def test_with_hosting_off_claude_is_told_so(engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    _, auth = await granted(engine, ada)
    async for client in _client(create_app(HOSTING_OFF, http=fake_http(fly=FakeFly()))):
        assert (await tool(client, auth, "runtimes"))["content"][0]["text"] == OFF_SAID
        assert (await tool(client, auth, "runtime"))["content"][0]["text"] == OFF_SAID
        args = {"name": "research", "size": "small"}
        made = (await rpc(client, auth, "tools/call", name="create_runtime", arguments=args))["result"]
        assert _refused(made, "E_UNAVAILABLE")["reason"] == "hosting_off"
        assert _refused(await tool(client, auth, "start_runtime"), "E_UNAVAILABLE")["reason"] == "hosting_off"
        rt = await hosted_runtime(engine, ada, "older")
        again = await tool(client, auth, "restart_runtime", id=str(rt.id))
        assert _refused(again, "E_UNAVAILABLE")["reason"] == "hosting_off"


async def test_with_hosting_off_the_tick_meters_nothing(engine: AsyncEngine, redis: Redis) -> None:
    rt = await hosted_runtime(engine, await person(engine, "Pro"), "ticked")
    async with engine.begin() as conn:
        values = {"state": "online", "metered_at": func.now() - timedelta(seconds=60)}
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(**values))
    assert await tend.tend(engine, Hub(redis), HOSTING_OFF, 60, None, None)
    async with engine.connect() as conn:
        seconds = (await conn.execute(select(Rrotor.month_seconds).where(Rrotor.id == rt.id))).scalar_one()
    assert seconds == 0  # not metered


def _session(stripe: FakeStripe) -> dict[str, Any]:
    return next(body for _, path, body in stripe.calls if path == "/checkout/sessions")


async def test_with_hosting_off_checkout_sells_the_flat_price_only(engine: AsyncEngine) -> None:
    stripe = FakeStripe()
    ada = await person(engine)
    unpriced = HOSTING_OFF.model_copy(update={"stripe_price_hosting": None})  # no hosting price needed
    async for client in _client(create_app(unpriced, http=fake_http(stripe))):
        res = await client.post("/v1/billing/checkout", json={"plan": "Pro"}, headers=ada.headers)
        assert res.status_code == 200, res.text
    session = _session(stripe)
    assert session["line_items[0][price]"] == "price_test_pro" and "line_items[1][price]" not in session


async def test_an_enterprise_grant_needs_no_markup_while_hosting_is_off(engine: AsyncEngine) -> None:
    stripe = FakeStripe()
    ada = await person(engine)
    sub, customer = f"sub_deal_{ada.org_id.hex}", f"cus_deal_{ada.org_id.hex}"
    stripe.sub(sub, customer, "price_deal", 1)
    argv = ["grant", "--org", str(ada.org_id), "--until", "2027-10-31", "--subscription", sub]
    said = await enterprise.run(argv, HOSTING_OFF, fake_http(stripe))
    assert said == f"Ada Lovelace's org is on Enterprise through 2027-10-31, billed on {sub} ({customer})."
    assert (await org_row(engine, ada.org_id)).markup_pct is None
