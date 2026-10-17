"""A hosted rrotor asking whether a bearer it was shown is a Glyphh sign-in for its own address: yes for a token
issued for that address to a person of the runtime's org, no for anything else; the runtime's own token as auth."""

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Rrotor
from glyphh_server.ops.connector import grants
from tests.connector import granted
from tests.db.helpers import person
from tests.link import Rt, hosted_runtime, local_runtime

MACHINE = "m1a2b3c4d5"
ADDRESS = f"https://{MACHINE}.glyphh.app/mcp"


async def machine(engine: AsyncEngine, who) -> Rt:  # type: ignore[no-untyped-def]
    rt = await hosted_runtime(engine, who)
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(fly_machine_id=MACHINE))
    return rt


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
    rt = await machine(engine, who)
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
    rt = await machine(engine, who)
    _, own = await granted(engine, who)  # the Glyphh connector's own token: not for the runtime
    assert (await ask(client, rt, token_of(own))).json() == {"active": False}
    other = await person(engine, "Pro")
    _, theirs = await granted(engine, other, resource=ADDRESS)  # another org's person, this very address
    assert (await ask(client, rt, token_of(theirs))).json() == {"active": False}
    _, elsewhere = await granted(engine, who, resource="https://z9y8x7w6v5.glyphh.app/mcp")  # another machine
    assert (await ask(client, rt, token_of(elsewhere))).json() == {"active": False}
    assert (await ask(client, rt, "not-a-token")).json() == {"active": False}
    _, mine = await granted(engine, who, resource=ADDRESS)
    local = await local_runtime(engine, who)
    assert (await ask(client, local, token_of(mine))).json() == {"active": False}
    newcomer = await person(engine, "Pro")
    unplaced = await hosted_runtime(engine, newcomer)  # no machine yet: no address to be signed in for
    _, early = await granted(engine, newcomer, resource=ADDRESS)
    assert (await ask(client, unplaced, token_of(early))).json() == {"active": False}


async def test_the_runtimes_own_token_is_the_auth(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    res = await client.post("/v1/runtime/introspect", json={"token": "t"})
    assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED"
    res = await client.post(
        "/v1/runtime/introspect", json={"token": "t"}, headers={"authorization": f"Bearer {uuid.uuid4()}"}
    )
    assert res.status_code == 401
    who = await person(engine, "Pro")
    rt = await machine(engine, who)
    res = await client.post("/v1/runtime/introspect", json={}, headers={"authorization": f"Bearer {rt.token}"})
    assert res.status_code == 422
