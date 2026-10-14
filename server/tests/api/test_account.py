"""The signed-in person: who they are, their installs, signing out, and tokens that no longer work."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Install, Token
from tests.db.helpers import another_install, member, person


async def test_me_has_the_org_role_plan_limits_and_what_is_used(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team", seats=3)
    await member(engine, ada.org_id)
    await client.post("/v1/workspaces", json={"name": "Inbox"}, headers=ada.headers)
    await client.post("/v1/org/invites", json={"email": "new@people.test"}, headers=ada.headers)
    me = (await client.get("/v1/me", headers=ada.headers)).json()
    assert (me["email"], me["name"], me["role"], me["providers"]) == (ada.email, "Ada Lovelace", "admin", [])
    assert me["org"] == {"id": str(ada.org_id), "name": "Ada Lovelace's org", "seats": 3, "billing_status": "none"}
    assert me["plan"] == {
        "name": "Team",
        "version": 1,
        "seat_price_cents": 1600,
        "limits": {"members": None, "installs": 10, "workspaces": None},
        "features": {"rpa": True},
    }
    assert me["used"] == {"members": 2, "seats": 3, "installs": 1, "workspaces": 1}


async def test_a_person_renames_themselves(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await client.patch("/v1/me", json={"name": "  Countess  "}, headers=ada.headers)
    assert res.json()["name"] == "Countess"
    assert (await client.patch("/v1/me", json={"name": ""}, headers=ada.headers)).status_code == 422


async def test_installs_are_listed_and_one_revoked_signs_that_machine_out(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    other_id, other = await another_install(engine, ada.user_id)
    listed = (await client.get("/v1/installs", headers=ada.headers)).json()
    assert [(i["name"], i["surface"], i["current"]) for i in listed] == [
        ("Mac", "desktop", True),
        ("Linux box", "desktop", False),
    ]
    assert listed[0]["last_seen_at"] is not None and listed[1]["last_seen_at"] is None
    assert (await client.delete(f"/v1/installs/{other_id}", headers=ada.headers)).status_code == 204
    assert (await client.get("/v1/me", headers=other)).status_code == 401
    again = await client.delete(f"/v1/installs/{other_id}", headers=ada.headers)
    assert again.status_code == 404 and again.json()["error"]["code"] == "E_NOT_FOUND"
    assert [i["name"] for i in (await client.get("/v1/installs", headers=ada.headers)).json()] == ["Mac"]


async def test_someone_elses_install_cannot_be_revoked(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada, bob = await person(engine), await person(engine)
    assert (await client.delete(f"/v1/installs/{bob.install_id}", headers=ada.headers)).status_code == 404
    assert (await client.get("/v1/me", headers=bob.headers)).status_code == 200


async def test_signing_out_revokes_this_install_and_its_tokens(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    assert (await client.post("/v1/sign-out", headers=ada.headers)).status_code == 204
    res = await client.get("/v1/me", headers=ada.headers)
    assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED"
    async with engine.connect() as conn:
        revoked = select(Token.revoked_at, Install.revoked_at).join(Install).where(Install.id == ada.install_id)
        assert all((await conn.execute(revoked)).one())


async def test_a_missing_wrong_or_expired_token_is_one_answer(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    async with engine.begin() as conn:
        await conn.execute(
            update(Token).where(Token.install_id == ada.install_id).values(expires_at=datetime.now(UTC) - timedelta(1))
        )
    for headers in ({}, {"authorization": "Basic x"}, {"authorization": "Bearer nope"}, ada.headers):
        res = await client.get("/v1/me", headers=headers)
        assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED", headers


async def test_an_install_is_marked_seen_at_most_once_a_minute(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    seen = select(Install.last_seen_at).where(Install.id == ada.install_id)
    await client.get("/v1/me", headers=ada.headers)
    async with engine.connect() as conn:
        first = (await conn.execute(seen)).scalar_one()
    await client.get("/v1/me", headers=ada.headers)
    async with engine.connect() as conn:
        assert (await conn.execute(seen)).scalar_one() == first
