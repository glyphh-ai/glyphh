"""A self-hosted rrotor asking whether a bearer it was shown is a Glyphh sign-in for its own address: yes for a token
issued for that address to a person of the runtime's org, no for anything else; the runtime's own token as auth."""

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.connector import grants
from tests.connector import granted
from tests.db.helpers import person
from tests.link import Rt, local_runtime, self_runtime

HOST = "https://rrotor.acme.test"
ADDRESS = f"{HOST}/mcp"


def token_of(auth: dict[str, str]) -> str:
    return auth["authorization"].split()[1]


async def ask(client: httpx.AsyncClient, rt: Rt, token: str) -> httpx.Response:
    return await client.post(
        "/v1/runtime/introspect", json={"token": token}, headers={"authorization": f"Bearer {rt.token}"}
    )


async def test_a_sign_in_for_this_runtime_is_active_and_says_whose(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    who = await person(engine, "Pro")
    rt = await self_runtime(engine, who, HOST)
    grant_id, auth = await granted(engine, who, resource=ADDRESS)
    res = await ask(client, rt, token_of(auth))
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store", res.text
    body = res.json()
    assert (body["active"], body["sub"], body["org"], body["scope"]) == (
        True,
        str(who.user_id),
        str(who.org_id),
        "account",
    )
    assert body["exp"] > int(datetime.now(UTC).timestamp())
    async with engine.begin() as conn:
        await grants.end(conn, grant_id)
    assert (await ask(client, rt, token_of(auth))).json() == {"active": False}  # revoked: no longer


async def test_anything_else_is_not_active(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    who = await person(engine, "Pro")
    rt = await self_runtime(engine, who, HOST)
    _, own = await granted(engine, who)  # the Glyphh connector's own token: not for the runtime
    assert (await ask(client, rt, token_of(own))).json() == {"active": False}
    other = await person(engine, "Pro")
    _, theirs = await granted(engine, other, resource=ADDRESS)  # another org's person, this very address
    assert (await ask(client, rt, token_of(theirs))).json() == {"active": False}
    _, elsewhere = await granted(engine, who, resource="https://other.acme.test/mcp")  # another runtime
    assert (await ask(client, rt, token_of(elsewhere))).json() == {"active": False}
    assert (await ask(client, rt, "not-a-token")).json() == {"active": False}
    _, mine = await granted(engine, who, resource=ADDRESS)
    local = await local_runtime(engine, who)  # a local runtime has no address to be signed in for
    assert (await ask(client, local, token_of(mine))).json() == {"active": False}


async def test_the_runtimes_own_token_is_the_auth(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    res = await client.post("/v1/runtime/introspect", json={"token": "t"})
    assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED"
    res = await client.post(
        "/v1/runtime/introspect", json={"token": "t"}, headers={"authorization": f"Bearer {uuid.uuid4()}"}
    )
    assert res.status_code == 401
    who = await person(engine, "Pro")
    rt = await self_runtime(engine, who, HOST)
    res = await client.post("/v1/runtime/introspect", json={}, headers={"authorization": f"Bearer {rt.token}"})
    assert res.status_code == 422
