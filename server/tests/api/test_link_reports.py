"""What a runtime reports over its link: each key's calls, counted once, its precedents, and every model it deployed,
recorded when the server had not seen it."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Deployment, Model, ModelVersion, RuntimeKey
from glyphh_server.ops.runtime_keys import key_hash
from tests.db.helpers import person
from tests.link import SHA, SHA2, WAIT, a_model, connect, hello, hosted_runtime, linked, receive, runtime_row, server

SHA3: str = "c" * 40


async def _key(engine: AsyncEngine, runtime_id: uuid.UUID, user_id: uuid.UUID, name: str) -> str:
    async with engine.begin() as conn:
        values = {"rrotor_id": runtime_id, "user_id": user_id, "name": name, "key_hash": key_hash(name)}
        await conn.execute(insert(RuntimeKey).values(values))
    return key_hash(name)


async def _keys(engine: AsyncEngine, runtime_id: uuid.UUID) -> dict[str, tuple[int, datetime | None]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(RuntimeKey.name, RuntimeKey.calls, RuntimeKey.last_used_at).where(RuntimeKey.rrotor_id == runtime_id)
        )
        return {name: (calls, last) for name, calls, last in rows}


def _usage(message_id: str, seq: int, *uses: tuple[str, int, str]) -> dict[str, Any]:
    keys = [{"key_sha256": sha, "calls": calls, "last_used_at": at} for sha, calls, at in uses]
    return {"type": "usage", "id": message_id, "seq": seq, "keys": keys}


async def _send(ws: Any, message: dict[str, Any]) -> None:
    await ws.send_json(message)
    assert (await receive(ws, "ack"))["of"] == message["id"]


async def test_usage_adds_each_keys_calls_once(engine: AsyncEngine) -> None:
    ada, eve = await person(engine), await person(engine)
    rt, theirs = await hosted_runtime(engine, ada), await hosted_runtime(engine, eve)
    crm = await _key(engine, rt.id, ada.user_id, "crm")
    bot = await _key(engine, rt.id, ada.user_id, "bot")
    eves = await _key(engine, theirs.id, eve.user_id, "eve")
    early, late = "2026-10-16T10:00:00+00:00", "2026-10-16T10:05:00+00:00"
    async with server() as srv, linked(srv, rt) as ws:
        await _send(ws, _usage("u1", 1, (crm, 3, late), (eves, 9, late), ("f" * 64, 1, late)))
        await _send(ws, _usage("u1", 1, (crm, 3, late)))  # a replay after a reconnect: skipped
        await _send(ws, _usage("u2", 2, (crm, 2, early), (bot, 1, early)))
    found = await _keys(engine, rt.id)
    assert found == {
        "crm": (5, datetime(2026, 10, 16, 10, 5, tzinfo=UTC)),  # the later use kept
        "bot": (1, datetime(2026, 10, 16, 10, 0, tzinfo=UTC)),
    }
    assert await _keys(engine, theirs.id) == {"eve": (0, None)}  # another runtime's key is never this one's


async def test_usage_keeps_the_runtimes_precedents_as_it_last_said_them(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await hosted_runtime(engine, ada)
    async with server() as srv, linked(srv, rt) as ws:
        await _send(ws, {"type": "usage", "id": "p1", "seq": 1, "keys": [], "precedents": 1_200})
        row = await runtime_row(engine, rt.id)
        assert (row.precedents, row.precedents_at is not None) == (1_200, True)
        await _send(ws, _usage("p2", 2))  # no reading yet: the last one stands
        await _send(ws, {"type": "usage", "id": "p3", "seq": 3, "precedents": 900})
        await ws.send_json({"type": "usage", "id": "p4", "seq": 4, "precedents": -1})  # unreadable: skipped
        await _send(ws, {"type": "usage", "id": "p5", "seq": 5, "keys": [], "precedents": 950})
    assert (await runtime_row(engine, rt.id)).precedents == 950


async def _models(engine: AsyncEngine, user_id: uuid.UUID) -> list[tuple[str, str | None, int, str, dict[str, Any]]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Model.name, Model.repo, ModelVersion.version, ModelVersion.commit_sha, ModelVersion.manifest)
            .join(ModelVersion, ModelVersion.model_id == Model.id)
            .where(Model.user_id == user_id)
            .order_by(Model.name, ModelVersion.version)
        )
        return [tuple(r) for r in rows]  # type: ignore[misc]


async def test_a_model_deployed_on_the_runtime_is_recorded_and_active(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await hosted_runtime(engine, ada)
    manifest = {"description": "Triage invoices", "functions": ["triage"]}
    deployed = {"type": "deployed", "id": "d1", "model": "triage", "version": 1, "commit_sha": SHA}
    async with server() as srv, linked(srv, rt) as ws:
        await _send(ws, {**deployed, "repo": "ada/triage", "manifest": manifest})
        await _send(ws, {**deployed, "id": "d2", "version": 2, "commit_sha": SHA2})  # a bundle: no repo, no manifest
    assert await _models(engine, ada.user_id) == [
        ("triage", "ada/triage", 1, SHA, manifest),
        ("triage", "ada/triage", 2, SHA2, {}),
    ]
    async with engine.connect() as conn:
        active = await conn.execute(
            select(ModelVersion.commit_sha, Deployment.active)
            .join(Deployment, Deployment.model_version_id == ModelVersion.id)
            .where(Deployment.rrotor_id == rt.id)
        )
        assert dict(active.all()) == {SHA: False, SHA2: True}


async def test_a_runtimes_number_taken_by_another_commit_gets_the_next_free_one(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await hosted_runtime(engine, ada)
    await a_model(engine, ada)  # daily_sales v1 and v2 already on record
    deployed = {"type": "deployed", "id": "d1", "model": "daily_sales", "version": 1, "commit_sha": SHA3}
    async with server() as srv, linked(srv, rt) as ws:
        await _send(ws, deployed)
        await _send(ws, {**deployed, "id": "d2"})  # the same commit again: the same version
    assert [(v, sha) for _, _, v, sha, _ in await _models(engine, ada.user_id)] == [(1, SHA), (2, SHA2), (3, SHA3)]


async def test_a_hello_records_the_models_already_active_on_the_runtime(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await hosted_runtime(engine, ada)
    active = [{"model": "incidents", "version": 3, "commit_sha": SHA3}]
    async with server() as srv, connect(srv, rt.token) as ws:
        await ws.send_json(hello(rt, deployed=active))
        assert (await ws.receive_json(timeout=WAIT))["type"] == "welcome"
    assert await _models(engine, ada.user_id) == [("incidents", None, 3, SHA3, {})]
    async with engine.connect() as conn:
        on = await conn.execute(select(Deployment.active).where(Deployment.rrotor_id == rt.id))
        assert on.scalars().all() == [True]
