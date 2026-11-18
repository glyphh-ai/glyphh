"""The signed-in person: who they are, and tokens that do not work (or no longer do)."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api.gone import RETIRED
from glyphh_server.models import ConnectorGrant, ConnectorToken, Org
from glyphh_server.ops.auth.signin import ProviderProfile, sign_in
from glyphh_server.ops.connector import grants, tokens
from tests.api.browser import Staff
from tests.db.helpers import member, person


async def test_me_has_the_person_their_providers_org_and_role(staff: Staff, engine: AsyncEngine) -> None:
    ada = staff.who
    async with engine.begin() as conn:
        for provider in ("google", "github"):
            profile = {"provider": provider, "subject": f"{provider}-{ada.email}", "email": ada.email}
            assert await sign_in(conn, ProviderProfile(**profile, email_verified=True)) == ada.user_id
    res = await staff.http.get("/v1/me", headers=ada.headers)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "id": str(ada.user_id),
        "email": ada.email,
        "name": "Ada Lovelace",
        "role": "admin",
        "providers": ["github", "google"],
        "org": {
            "id": str(ada.org_id),
            "name": "Ada Lovelace's org",
            "billing_status": "none",
            "renews_at": None,
            "plan_until": None,
        },
        "staff": True,
    }


async def test_a_token_that_is_not_staffs_is_no_good_any_more(
    client: httpx.AsyncClient, staff: Staff, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    grace = await member(engine, staff.who.org_id)  # in staff's org, but not staff
    for http, who in ((client, ada), (staff.http, ada), (staff.http, grace), (client, staff.who)):
        res = await http.get("/v1/me", headers=who.headers)
        assert res.status_code == 410, res.text
        assert res.json() == {
            "error": {"code": "E_WOUND_DOWN", "message": RETIRED, "trace_id": res.headers["x-request-id"]}
        }


async def test_a_missing_wrong_or_expired_token_is_one_answer(staff: Staff, engine: AsyncEngine) -> None:
    ada = staff.who
    assert (await staff.http.get("/v1/me", headers=ada.headers)).status_code == 200
    async with engine.begin() as conn:
        mine = ConnectorToken.grant_id == ada.grant_id
        await conn.execute(update(ConnectorToken).where(mine).values(expires_at=datetime.now(UTC) - timedelta(1)))
    for headers in ({}, {"authorization": "Basic x"}, {"authorization": "Bearer nope"}, ada.headers):
        res = await staff.http.get("/v1/me", headers=headers)
        assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED", headers
        assert res.json()["error"]["message"] == "Sign in to Glyphh again: this token is not valid."


async def test_a_refresh_token_or_one_whose_grant_ended_opens_nothing(staff: Staff, engine: AsyncEngine) -> None:
    ada = staff.who
    async with engine.begin() as conn:
        fresh = await tokens.issue(conn, ada.grant_id, "account")
    refresh = await staff.http.get("/v1/me", headers={"authorization": f"Bearer {fresh.refresh_token}"})
    assert refresh.status_code == 401
    async with engine.begin() as conn:
        await grants.end(conn, ada.grant_id)
    assert (await staff.http.get("/v1/me", headers=ada.headers)).status_code == 401


async def test_a_suspended_orgs_people_are_refused(staff: Staff, engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == staff.who.org_id).values(suspended_at=func.now()))
    res = await staff.http.get("/v1/me", headers=staff.who.headers)
    assert res.status_code == 403
    err = res.json()["error"]
    assert (err["code"], err["reason"]) == ("E_FORBIDDEN", "suspended") and "support@glyphh.ai" in err["message"]


async def test_a_grant_is_marked_used_at_most_once_a_minute(staff: Staff, engine: AsyncEngine) -> None:
    seen = select(ConnectorGrant.last_used_at).where(ConnectorGrant.id == staff.who.grant_id)
    async with engine.connect() as conn:
        assert (await conn.execute(seen)).scalar_one() is None
    await staff.http.get("/v1/me", headers=staff.who.headers)
    async with engine.connect() as conn:
        first = (await conn.execute(seen)).scalar_one()
    await staff.http.get("/v1/me", headers=staff.who.headers)
    async with engine.connect() as conn:
        assert first is not None and (await conn.execute(seen)).scalar_one() == first
