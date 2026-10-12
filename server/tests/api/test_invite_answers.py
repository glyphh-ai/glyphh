"""A signed-in person answers an invite sent to them, and sees every org they're in."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops import invites
from glyphh_server.ops.auth import tokens
from tests.db.helpers import admin_of, make_user


async def _signed_in(engine: AsyncEngine, email: str) -> dict[str, str]:
    home = await admin_of(engine, f"Home of {email}")
    person = await make_user(engine, home.org_id, email)
    async with engine.begin() as conn:
        return {"authorization": f"Bearer {(await tokens.issue(conn, person, home.org_id)).access_token}"}


async def _invite(engine: AsyncEngine, org: str, email: str) -> str:
    boss = await admin_of(engine, org)
    async with engine.begin() as conn:
        return (await invites.create_invite(conn, boss, email, "user"))[1]


async def test_accepting_joins_and_lists_the_org(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    auth = await _signed_in(engine, "yes@answer.test")
    token = await _invite(engine, "Yes Co", "yes@answer.test")
    joined = await client.post("/v1/invites/accept", headers=auth, json={"invite": token})
    assert joined.status_code == 200 and joined.json() == {"org": "Yes Co"}
    orgs = {o["name"]: o for o in (await client.get("/v1/me/orgs", headers=auth)).json()}
    assert orgs["Yes Co"]["people"] == 2 and orgs["Yes Co"]["role"] == "user" and not orgs["Yes Co"]["personal"]


async def test_declining_closes_the_invite_and_someone_else_cannot(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = await _signed_in(engine, "no@answer.test")
    other = await _signed_in(engine, "other@answer.test")
    token = await _invite(engine, "No Co", "no@answer.test")
    wrong = await client.post("/v1/invites/decline", headers=other, json={"invite": token})
    assert wrong.status_code == 403 and wrong.json()["error"]["reason"] == "wrong_account"
    assert (await client.post("/v1/invites/decline", headers=auth, json={"invite": token})).status_code == 204
    again = await client.post("/v1/invites/accept", headers=auth, json={"invite": token})
    assert again.json()["error"]["reason"] == "invite_expired"
