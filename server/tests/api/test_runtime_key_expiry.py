"""A runtime key expires within a year, or never; past a year is refused. An expired one leaves the list rrotor holds,
and the minute tick sends that list down the link. A revoked or expired key can then be deleted."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import RuntimeKey
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.runtime_keys import hashes_for, key_hash, push_expired
from tests.api.test_mcp_runtime import key_tool
from tests.api.test_mcp_tools import _refused
from tests.connector import granted
from tests.db.helpers import Person, person
from tests.link import holding, self_runtime


async def _key(client: httpx.AsyncClient, who: Person, runtime_id: uuid.UUID, **body: Any) -> httpx.Response:
    return await client.post("/v1/runtime/keys", json={**body, "runtime_id": str(runtime_id)}, headers=who.headers)


async def test_a_key_lasts_up_to_a_year_or_never(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    runtime_id = (await self_runtime(engine, ada)).id
    for days in (0, 366):
        res = (await _key(client, ada, runtime_id, name="CRM", expires_in_days=days)).json()["error"]
        assert (res["reason"], res["days"], res["message"]) == (
            "expiry_range",
            days,
            "An API key lasts 1 to 365 days, or never expires.",
        )
    never = await _key(client, ada, runtime_id, name="CRM")
    assert never.status_code == 201 and never.json()["expires_at"] is None
    assert [k["expires_at"] for k in (await client.get("/v1/runtime/keys", headers=ada.headers)).json()] == [None]
    async with engine.connect() as conn:
        assert await hashes_for(conn, runtime_id) == [key_hash(never.json()["key"])]


async def test_a_key_is_made_with_its_expiry_and_listed_with_it(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    runtime_id = (await self_runtime(engine, ada)).id
    before = datetime.now(UTC)
    made = (await _key(client, ada, runtime_id, name="CRM", expires_in_days=30)).json()
    expires = datetime.fromisoformat(made["expires_at"])
    assert before + timedelta(days=30) <= expires <= datetime.now(UTC) + timedelta(days=30)
    listed = (await client.get("/v1/runtime/keys", headers=ada.headers)).json()
    assert listed[0]["expires_at"] == made["expires_at"]


async def _expire(engine: AsyncEngine, key_id: str, ago: timedelta) -> None:
    async with engine.begin() as conn:
        when = datetime.now(UTC) - ago
        await conn.execute(update(RuntimeKey).where(RuntimeKey.id == uuid.UUID(key_id)).values(expires_at=when))


async def test_an_expired_key_leaves_the_list_and_the_tick_sends_it(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Any
) -> None:
    ada = await person(engine, "Pro")
    runtime_id = (await self_runtime(engine, ada)).id
    keys = [
        (await _key(client, ada, runtime_id, name=name, expires_in_days=30)).json() for name in ("old", "new", "live")
    ]
    old, new, live = keys
    await _expire(engine, old["id"], timedelta(hours=1))  # expired long before this tick: sent already
    hub = Hub(redis)
    assert await push_expired(engine, hub, timedelta(minutes=2)) == []
    await _expire(engine, new["id"], timedelta(seconds=30))
    async with holding(redis, runtime_id) as sent:
        assert await push_expired(engine, hub, timedelta(minutes=2)) == [runtime_id]
        assert (await sent())["hashes"] == [key_hash(live["key"])]
    async with engine.connect() as conn:
        assert await hashes_for(conn, runtime_id) == [key_hash(live["key"])]


async def test_the_connector_makes_a_key_that_expires_or_never_does(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    _, auth = await granted(engine, ada)
    runtime_id = str((await self_runtime(engine, ada)).id)
    never = await key_tool(client, auth, name="Claude", runtime_id=runtime_id)
    assert "Shown once, expires never." in never["content"][0]["text"]
    _refused(await key_tool(client, auth, name="Claude", expires_in_days=400, runtime_id=runtime_id), "E_INVALID")


async def test_only_a_revoked_or_expired_key_is_deleted_and_only_ones_own(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    runtime_id = (await self_runtime(engine, ada)).id
    made = [
        (await _key(client, ada, runtime_id, name=name, expires_in_days=30)).json()
        for name in ("live", "revoked", "expired")
    ]
    live, revoked, expired = made
    forever = (await _key(client, ada, runtime_id, name="forever")).json()
    kept = await client.delete(f"/v1/runtime/keys/{forever['id']}/record", headers=ada.headers)
    assert (kept.status_code, kept.json()["error"]["reason"]) == (409, "live")
    await client.delete(f"/v1/runtime/keys/{revoked['id']}", headers=ada.headers)
    await _expire(engine, expired["id"], timedelta(days=1))

    refused = await client.delete(f"/v1/runtime/keys/{live['id']}/record", headers=ada.headers)
    assert (refused.status_code, refused.json()["error"]["reason"]) == (409, "live")
    theirs = await client.delete(f"/v1/runtime/keys/{revoked['id']}/record", headers=eve.headers)
    assert theirs.status_code == 404
    for key in (revoked, expired):
        gone = await client.delete(f"/v1/runtime/keys/{key['id']}/record", headers=ada.headers)
        assert gone.status_code == 204
    listed = (await client.get("/v1/runtime/keys", headers=ada.headers)).json()
    assert [k["name"] for k in listed] == ["live", "forever"]
    again = await client.delete(f"/v1/runtime/keys/{revoked['id']}/record", headers=ada.headers)
    assert again.status_code == 404
    revoked_again = await client.delete(f"/v1/runtime/keys/{revoked['id']}", headers=ada.headers)
    assert revoked_again.status_code == 404
