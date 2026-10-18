"""A runtime key expires within a year, or never; past a year is refused. An expired one leaves the list rrotor holds,
and the minute tick sends that list down the link. A revoked or expired key can then be deleted."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import RuntimeKey
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.runtime_keys import hashes_for, key_hash, push_expired
from tests.api.test_hosted import FLY_SETTINGS
from tests.api.test_mcp_runtime import key_tool
from tests.api.test_mcp_tools import _refused
from tests.conftest import _client
from tests.connector import granted
from tests.db.helpers import person
from tests.fakes import FakeFly, fake_http
from tests.link import holding


async def _started(client: Any, headers: dict[str, str]) -> str:
    return (await client.post("/v1/runtime/start", headers=headers)).json()["runtime_id"]


async def test_a_key_lasts_up_to_a_year_or_never(engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))):
        runtime_id = uuid.UUID(await _started(client, ada.headers))
        for days in (0, 366):
            body = {"name": "CRM", "expires_in_days": days}
            res = (await client.post("/v1/runtime/keys", json=body, headers=ada.headers)).json()["error"]
            assert (res["reason"], res["days"], res["message"]) == (
                "expiry_range",
                days,
                "An API key lasts 1 to 365 days, or never expires.",
            )
        never = await client.post("/v1/runtime/keys", json={"name": "CRM"}, headers=ada.headers)
        assert never.status_code == 201 and never.json()["expires_at"] is None
        assert [k["expires_at"] for k in (await client.get("/v1/runtime/keys", headers=ada.headers)).json()] == [None]
    async with engine.connect() as conn:
        assert await hashes_for(conn, runtime_id) == [key_hash(never.json()["key"])]


async def test_a_key_is_made_with_its_expiry_and_listed_with_it(engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))):
        await _started(client, ada.headers)
        before = datetime.now(UTC)
        made = (
            await client.post("/v1/runtime/keys", json={"name": "CRM", "expires_in_days": 30}, headers=ada.headers)
        ).json()
        expires = datetime.fromisoformat(made["expires_at"])
        assert before + timedelta(days=30) <= expires <= datetime.now(UTC) + timedelta(days=30)
        listed = (await client.get("/v1/runtime/keys", headers=ada.headers)).json()
        assert listed[0]["expires_at"] == made["expires_at"]


async def _expire(engine: AsyncEngine, key_id: str, ago: timedelta) -> None:
    async with engine.begin() as conn:
        when = datetime.now(UTC) - ago
        await conn.execute(update(RuntimeKey).where(RuntimeKey.id == uuid.UUID(key_id)).values(expires_at=when))


async def test_an_expired_key_leaves_the_list_and_the_tick_sends_it(engine: AsyncEngine, redis: Any) -> None:
    ada = await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))):
        runtime_id = uuid.UUID(await _started(client, ada.headers))
        keys = []
        for name in ("old", "new", "live"):
            body = {"name": name, "expires_in_days": 30}
            keys.append((await client.post("/v1/runtime/keys", json=body, headers=ada.headers)).json())
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


async def test_the_connector_makes_a_key_that_expires_or_never_does(engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    _, auth = await granted(engine, ada)
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))):
        await _started(client, ada.headers)
        never = await key_tool(client, auth, name="Claude")
        assert "Shown once, expires never." in never["content"][0]["text"]
        _refused(await key_tool(client, auth, name="Claude", expires_in_days=400), "E_INVALID")


async def test_only_a_revoked_or_expired_key_is_deleted_and_only_ones_own(engine: AsyncEngine) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))):
        await _started(client, ada.headers)
        made = []
        for name in ("live", "revoked", "expired"):
            body = {"name": name, "expires_in_days": 30}
            made.append((await client.post("/v1/runtime/keys", json=body, headers=ada.headers)).json())
        live, revoked, expired = made
        forever = (await client.post("/v1/runtime/keys", json={"name": "forever"}, headers=ada.headers)).json()
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
