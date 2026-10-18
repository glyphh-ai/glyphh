"""Keys across a person's machines: a key names one machine (or a self-hosted runtime) or none, and one naming none
is held by every hosted machine of theirs, never by a self-hosted one."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import RuntimeKey
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import runtime_for
from glyphh_server.ops.link.protocol import Usage
from glyphh_server.ops.link.reports import apply_usage
from glyphh_server.ops.runtime_keys import hashes_for, key_hash, push_expired
from tests.api.test_hosted import FLY_SETTINGS
from tests.conftest import _client
from tests.db.helpers import person
from tests.fakes import FakeFly, fake_http
from tests.link import holding, hosted_runtime, self_runtime


async def _key(engine: AsyncEngine, user_id: uuid.UUID, rrotor_id: uuid.UUID | None, name: str, **more: Any) -> str:
    async with engine.begin() as conn:
        values = {"rrotor_id": rrotor_id, "user_id": user_id, "name": name, "key_hash": key_hash(name)}
        await conn.execute(insert(RuntimeKey).values(**values, **more))
    return key_hash(name)


async def test_a_key_naming_no_machine_is_held_by_every_hosted_one_and_no_self_hosted_one(
    engine: AsyncEngine, redis: Any
) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    a, b = await hosted_runtime(engine, ada, "a"), await hosted_runtime(engine, ada, "b")
    own, theirs = await self_runtime(engine, ada), await hosted_runtime(engine, eve)
    every = await _key(engine, ada.user_id, None, "every")
    only_b = await _key(engine, ada.user_id, b.id, "only-b")
    await _key(engine, eve.user_id, None, "eve's")
    async with engine.connect() as conn:
        assert await hashes_for(conn, a.id) == [every]
        assert await hashes_for(conn, b.id) == [every, only_b]
        assert await hashes_for(conn, own.id) == [] and await hashes_for(conn, theirs.id) == [key_hash("eve's")]
    past = datetime.now(UTC) - timedelta(seconds=30)
    await _key(engine, ada.user_id, None, "gone", expires_at=past)
    await _key(engine, ada.user_id, a.id, "gone-a", expires_at=past)
    async with holding(redis, a.id) as a_sent, holding(redis, b.id) as b_sent:
        pushed = await push_expired(engine, Hub(redis), timedelta(minutes=2))
        assert sorted(pushed) == sorted([a.id, b.id])  # each machine sent its list once
        assert (await a_sent())["hashes"] == [every] and (await b_sent())["hashes"] == [every, only_b]
    async with engine.begin() as conn:  # revoked, so no other test's tick sends them again
        revoked = update(RuntimeKey).where(RuntimeKey.user_id == ada.user_id, RuntimeKey.expires_at.is_not(None))
        await conn.execute(revoked.values(revoked_at=datetime.now(UTC)))
    use = {"key_sha256": every, "calls": 3, "last_used_at": datetime.now(UTC)}
    usage = Usage.model_validate({"type": "usage", "seq": 1, "keys": [use]})
    async with engine.begin() as conn:
        await apply_usage(conn, await runtime_for(engine, a.token), usage)
        await apply_usage(conn, await runtime_for(engine, own.token), usage)  # not the self-hosted one's to count
        calls = (await conn.execute(select(RuntimeKey.calls).where(RuntimeKey.key_hash == every))).scalar_one()
    assert calls == 3


async def test_keys_made_for_a_machine_or_every_one_reach_those_machines(engine: AsyncEngine, redis: Any) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))):
        a = (await client.post("/v1/runtimes", json={"name": "a", "size": "small"}, headers=ada.headers)).json()
        b = (await client.post("/v1/runtimes", json={"name": "b", "size": "small"}, headers=ada.headers)).json()
        a_id, b_id = uuid.UUID(a["id"]), uuid.UUID(b["id"])
        async with holding(redis, a_id) as a_sent, holding(redis, b_id) as b_sent:
            body = {"name": "B only", "runtime_id": b["id"]}
            only_b = (await client.post("/v1/runtime/keys", json=body, headers=ada.headers)).json()
            assert only_b["runtime_id"] == b["id"] and (await b_sent())["hashes"] == [key_hash(only_b["key"])]
            every = (await client.post("/v1/runtime/keys", json={"name": "every"}, headers=ada.headers)).json()
            assert (await a_sent())["hashes"] == [key_hash(every["key"])]
            assert len((await b_sent())["hashes"]) == 2
            await client.delete(f"/v1/runtime/keys/{every['id']}", headers=ada.headers)
            assert (await a_sent())["hashes"] == [] and (await b_sent())["hashes"] == [key_hash(only_b["key"])]
        res = await client.post("/v1/runtime/keys", json={"name": "x", "runtime_id": b["id"]}, headers=eve.headers)
        assert res.status_code == 404
