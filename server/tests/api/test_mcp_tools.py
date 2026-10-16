"""The connector's tools, called as Claude calls them: each answers a short text and the same as structured content,
and a refusal is a tool error carrying the API's error. Each person sees and changes only their own."""

from datetime import UTC, datetime

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Install, Org
from tests.conftest import SETTINGS, _client
from tests.connector import granted, rpc, tool
from tests.db.helpers import member, org_row, person, subscribed
from tests.fakes import FakeStripe, fake_http


def _refused(result: dict, code: str) -> dict:
    assert result["isError"] is True, result
    error = result["structuredContent"]["error"]
    assert error["code"] == code and error["trace_id"] and result["content"][0]["text"] == error["message"]
    return error


async def test_whoami_and_plan_show_the_account_each_mods_limits_and_what_is_used(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    async with engine.begin() as conn:
        renews = datetime(2026, 11, 15, tzinfo=UTC)
        await conn.execute(update(Org).where(Org.id == ada.org_id).values(renews_at=renews))
    who = await tool(client, auth, "whoami")
    assert who["isError"] is False and who["structuredContent"]["email"] == ada.email
    assert who["content"] == [{"type": "text", "text": f"Ada Lovelace ({ada.email}), admin of Ada Lovelace's org."}]
    plan = await tool(client, auth, "plan")
    text = plan["content"][0]["text"]
    assert "Free (version 1), $0 per seat a month: 1 seats, billing none, renews 2026-11-15." in text
    assert "Members 1 of 1; installs 1 of 1.\nAdd-ons: none." in text
    data = plan["structuredContent"]
    assert data["used"] == {"members": 1, "seats": 1, "installs": 1}
    assert data["org"]["renews_at"].startswith("2026-11-15")
    assert data["plan"]["mods"] == {} and data["addons"] == []


async def test_plans_lists_what_each_plan_includes(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    _, auth = await granted(engine, await person(engine))
    plans = await tool(client, auth, "plans")
    assert [p["name"] for p in plans["structuredContent"]["plans"]] == ["Free", "Pro", "Team"]
    assert "Team: $16 per seat a month; members unlimited, installs 10;" in plans["content"][0]["text"]


async def test_upgrade_opens_checkout_then_changes_plan_once_subscribed(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    customer = f"cus_{ada.org_id.hex}"
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == ada.org_id).values(stripe_customer_id=customer))
    opened = await tool(client, auth, "upgrade", plan="Pro")
    assert opened["structuredContent"] == {"url": "https://checkout.stripe.test/cs_1"}
    assert stripe.calls[-1][2]["line_items[0][quantity]"] == "1"
    sub = f"sub_{ada.org_id.hex}"
    await subscribed(engine, ada.org_id, sub, customer)
    stripe.sub(sub, customer, "price_test_pro", 1)
    changed = await tool(client, auth, "upgrade", plan="Team")
    assert changed["structuredContent"]["org"]["plan"]["name"] == "Team"
    assert changed["content"][0]["text"] == "Your org is on Team now, prorated."
    seats = await tool(client, auth, "seats", seats=3)
    assert seats["structuredContent"]["org"]["seats"] == 3 and "3 seats now, 1 taken" in seats["content"][0]["text"]
    portal = await tool(client, auth, "billing_portal")
    assert portal["structuredContent"] == {"url": "https://billing.stripe.test/p_1"}


async def test_billing_refusals_are_tool_errors(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    _refused(await tool(client, auth, "billing_portal"), "E_CONFLICT")
    _refused(await tool(client, auth, "upgrade", plan="Platinum"), "E_INVALID")
    _refused(await tool(client, auth, "seats", seats=2), "E_CONFLICT")
    grace = await member(engine, ada.org_id)
    _, theirs = await granted(engine, grace)
    _refused(await tool(client, theirs, "upgrade", plan="Pro"), "E_FORBIDDEN")
    problems = _refused(await tool(client, auth, "seats", seats=0), "E_INVALID")["problems"]
    assert problems[0]["loc"] == ["seats"]
    _refused(await tool(client, auth, "whoami", extra=1), "E_INVALID")
    assert (await org_row(engine, ada.org_id)).stripe_customer_id is None


async def test_without_stripe_billing_is_unavailable(engine: AsyncEngine) -> None:
    _, auth = await granted(engine, await person(engine))
    off = SETTINGS.model_copy(update={"stripe_secret_key": ""})
    async for c in _client(create_app(off, http=fake_http())):
        assert _refused(await tool(c, auth, "billing_portal"), "E_UNAVAILABLE")["reason"] == "billing_off"


async def test_installs_are_listed_and_one_signed_out(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    listed = await tool(client, auth, "installs")
    (one,) = listed["structuredContent"]["installs"]
    assert (
        one["id"] == str(ada.install_id) and one["current"] is False and "Mac (desktop" in listed["content"][0]["text"]
    )
    out = await tool(client, auth, "sign_out_install", install_id=str(ada.install_id))
    assert out["structuredContent"] == {"signed_out": str(ada.install_id)}
    assert (await client.get("/v1/me", headers=ada.headers)).status_code == 401
    assert (await tool(client, auth, "installs"))["content"][0]["text"] == "No installs."
    _refused(await tool(client, auth, "sign_out_install", install_id=str(ada.install_id)), "E_NOT_FOUND")


async def test_members_and_invites_and_only_the_admin_invites(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team", seats=3)
    _, auth = await granted(engine, ada)
    made = await tool(client, auth, "invite", email="New@People.test")
    assert made["structuredContent"]["link"].startswith("http://localhost:8080/join?invite=")
    assert made["structuredContent"]["invite"]["email"] == "new@people.test"
    people = await tool(client, auth, "members")
    assert [m["email"] for m in people["structuredContent"]["members"]] == [ada.email]
    assert [i["email"] for i in people["structuredContent"]["invites"]] == ["new@people.test"]
    assert "Invited: new@people.test" in people["content"][0]["text"]
    grace = await member(engine, ada.org_id)
    _, theirs = await granted(engine, grace)
    _refused(await tool(client, theirs, "invite", email="x@people.test"), "E_FORBIDDEN")
    _refused(await tool(client, auth, "invite", email="not-an-email"), "E_INVALID")


async def test_grants_are_each_persons_own_and_revoking_one_ends_its_tokens(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine), await person(engine)
    first, auth = await granted(engine, ada)
    second, other = await granted(engine, ada)
    eves, theirs = await granted(engine, eve)
    listed = (await tool(client, auth, "connector_grants"))["structuredContent"]["grants"]
    assert [(g["id"], g["current"]) for g in listed] == [(str(first), True), (str(second), False)]
    _refused(await tool(client, theirs, "revoke_grant", grant_id=str(first)), "E_NOT_FOUND")
    done = await tool(client, auth, "revoke_grant", grant_id=str(second))
    assert done["structuredContent"] == {"revoked": str(second)}
    assert (await client.post("/mcp", json={}, headers=other)).status_code == 401
    assert [g["id"] for g in (await tool(client, theirs, "connector_grants"))["structuredContent"]["grants"]] == [
        str(eves)
    ]


async def test_an_unknown_tool_is_a_protocol_error(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    _, auth = await granted(engine, await person(engine))
    assert (await rpc(client, auth, "tools/call", name="rm_rf", arguments={}))["error"]["code"] == -32602
    async with engine.connect() as conn:
        assert (await conn.execute(select(Install.id).limit(1))).first() is not None
