"""Someone already using Glyphh joins the org that invited them, leaving an org of their own behind."""

from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Org
from tests.db.helpers import Person, member, person, subscribed


async def _invite(client: httpx.AsyncClient, admin: Person, email: str) -> str:
    made = await client.post("/v1/org/invites", json={"email": email}, headers=admin.headers)
    assert made.status_code == 201, made.text
    return parse_qs(urlsplit(made.json()["link"]).query)["invite"][0]


async def test_a_solo_person_accepts_and_their_own_org_is_removed(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team")
    bob = await person(engine)
    token = await _invite(client, ada, bob.email)
    joined = await client.post("/v1/invites/accept", json={"token": token}, headers=bob.headers)
    assert joined.status_code == 200 and joined.json() == {"org_id": str(ada.org_id), "org": "Ada Lovelace's org"}
    me = (await client.get("/v1/me", headers=bob.headers)).json()
    assert (me["org"]["id"], me["role"]) == (str(ada.org_id), "member")
    async with engine.connect() as conn:
        assert (await conn.execute(select(Org.id).where(Org.id == bob.org_id))).first() is None
    used = await client.post("/v1/invites/accept", json={"token": token}, headers=bob.headers)
    assert used.status_code == 422 and used.json()["error"]["reason"] == "invite_expired"


async def test_only_the_invited_email_may_accept(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    eve = await person(engine)
    token = await _invite(client, ada, "someone-else@people.test")
    res = await client.post("/v1/invites/accept", json={"token": token}, headers=eve.headers)
    assert res.status_code == 403 and res.json()["error"]["reason"] == "wrong_account"


async def test_an_org_with_others_or_a_paid_one_cannot_be_left_this_way(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Team")
    crowded = await person(engine, "Team")
    await member(engine, crowded.org_id)
    paid = await person(engine, "Pro")
    await subscribed(engine, paid.org_id, "sub_paid_solo", "cus_paid_solo")
    for who in (crowded, paid):
        res = await client.post(
            "/v1/invites/accept", json={"token": await _invite(client, ada, who.email)}, headers=who.headers
        )
        assert res.status_code == 409 and res.json()["error"]["reason"] == "not_alone"


async def test_an_invite_into_your_own_org_is_already_yours(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    async with engine.begin() as conn:
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import insert

        from glyphh_server.models import Invite
        from glyphh_server.ops.auth.secrets import hash_secret

        await conn.execute(
            insert(Invite).values(
                org_id=ada.org_id,
                email=bob.email,
                token_hash=hash_secret("own-org"),
                expires_at=datetime.now(UTC) + timedelta(1),
            )
        )
    res = await client.post("/v1/invites/accept", json={"token": "own-org"}, headers=bob.headers)
    assert res.status_code == 409 and "already in" in res.json()["error"]["message"]
