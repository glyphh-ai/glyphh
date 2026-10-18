"""The org, its members and its invites; writes are the admin's, and members are unlimited on every plan."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Invite, User
from tests.db.helpers import member, person


async def test_the_org_is_read_by_anyone_in_it_and_renamed_by_its_admin(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    org = (await client.get("/v1/org", headers=bob.headers)).json()
    assert (org["name"], org["admin_user_id"], org["plan"]["name"]) == ("Ada Lovelace's org", str(ada.user_id), "Team")
    assert (org["members"], org["billing_status"], "seats" in org) == (2, "none", False)
    refused = await client.patch("/v1/org", json={"name": "Bob's"}, headers=bob.headers)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "E_FORBIDDEN"
    assert (await client.patch("/v1/org", json={"name": " Engines "}, headers=ada.headers)).json()["name"] == "Engines"


async def test_members_are_listed_and_a_removed_one_lands_in_an_org_of_their_own(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    listed = (await client.get("/v1/org/members", headers=bob.headers)).json()
    assert [(m["id"], m["role"]) for m in listed] == [(str(ada.user_id), "admin"), (str(bob.user_id), "member")]
    assert (await client.delete(f"/v1/org/members/{ada.user_id}", headers=bob.headers)).status_code == 403
    assert (await client.delete(f"/v1/org/members/{bob.user_id}", headers=ada.headers)).status_code == 204
    assert [m["id"] for m in (await client.get("/v1/org/members", headers=ada.headers)).json()] == [str(ada.user_id)]
    mine = (await client.get("/v1/me", headers=bob.headers)).json()
    assert (mine["role"], mine["plan"]["name"], mine["org"]["name"]) == ("admin", "Free", "Grace Hopper's org")
    assert (await client.get("/v1/org", headers=bob.headers)).json()["admin_user_id"] == str(bob.user_id)


async def test_the_admin_is_never_removed_and_strangers_are_not_found(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine), await person(engine)
    me = await client.delete(f"/v1/org/members/{ada.user_id}", headers=ada.headers)
    assert me.status_code == 403 and "admin" in me.json()["error"]["message"]
    assert (await client.delete(f"/v1/org/members/{eve.user_id}", headers=ada.headers)).status_code == 404


async def test_invites_are_made_listed_and_revoked_by_the_admin(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    made = await client.post("/v1/org/invites", json={"email": "New@People.Test"}, headers=ada.headers)
    assert made.status_code == 201
    body = made.json()
    assert body["invite"]["email"] == "new@people.test"
    assert body["link"].startswith("http://localhost:8080/join?invite=")
    listed = (await client.get("/v1/org/invites", headers=bob.headers)).json()
    assert [i["email"] for i in listed] == ["new@people.test"]
    assert (await client.post("/v1/org/invites", json={"email": "x@y.test"}, headers=bob.headers)).status_code == 403
    assert (await client.delete(f"/v1/org/invites/{body['invite']['id']}", headers=bob.headers)).status_code == 403
    assert (await client.delete(f"/v1/org/invites/{body['invite']['id']}", headers=ada.headers)).status_code == 204
    gone = await client.delete(f"/v1/org/invites/{body['invite']['id']}", headers=ada.headers)
    assert gone.status_code == 404
    assert (await client.get("/v1/org/invites", headers=ada.headers)).json() == []


async def test_an_invite_for_a_member_or_twice_for_one_email_clashes(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    taken = await client.post("/v1/org/invites", json={"email": bob.email.upper()}, headers=ada.headers)
    assert taken.status_code == 409 and "already in your org" in taken.json()["error"]["message"]
    await client.post("/v1/org/invites", json={"email": "twice@people.test"}, headers=ada.headers)
    again = await client.post("/v1/org/invites", json={"email": "twice@people.test"}, headers=ada.headers)
    assert again.status_code == 409 and "open invite" in again.json()["error"]["message"]
    bad = await client.post("/v1/org/invites", json={"email": "not-an-email"}, headers=ada.headers)
    assert bad.status_code == 422


async def test_an_expired_invite_holds_no_seat_and_can_be_sent_again(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team")
    await client.post("/v1/org/invites", json={"email": "late@people.test"}, headers=ada.headers)
    async with engine.begin() as conn:
        await conn.execute(
            update(Invite).where(Invite.org_id == ada.org_id).values(expires_at=datetime.now(UTC) - timedelta(1))
        )
    assert (await client.get("/v1/org/invites", headers=ada.headers)).json() == []
    again = await client.post("/v1/org/invites", json={"email": "late@people.test"}, headers=ada.headers)
    assert again.status_code == 201
    async with engine.connect() as conn:
        assert len((await conn.execute(select(Invite.id).where(Invite.org_id == ada.org_id))).all()) == 1


async def test_invites_are_never_limited_on_any_plan(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    for plan in ("Free", "Pro"):
        ada = await person(engine, plan)
        for n in range(3):
            res = await client.post("/v1/org/invites", json={"email": f"friend{n}@people.test"}, headers=ada.headers)
            assert res.status_code == 201, plan


async def test_a_new_person_signing_in_with_an_invited_email_joins_as_a_member(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe
) -> None:
    from tests.api.browser import open_browser, sign_in

    ada = await person(engine, "Team")
    async for browser in open_browser(stripe):
        await client.post("/v1/org/invites", json={"email": browser.email}, headers=ada.headers)
        me = (await browser.http.get("/v1/me", headers=await sign_in(browser.http))).json()
        assert (me["org"]["id"], me["role"], me["plan"]["name"]) == (str(ada.org_id), "member", "Team")
    assert (await client.get("/v1/org/invites", headers=ada.headers)).json() == []
    async with engine.connect() as conn:
        assert len((await conn.execute(select(User.id).where(User.org_id == ada.org_id))).all()) == 2
