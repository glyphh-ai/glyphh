"""Approvals, shown in Claude: the waiting ones listed newest first, streamed live, and answered once."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Approval
from glyphh_server.ops.approvals import ApprovalView, ask_approval, channel
from tests.api.sse import sse
from tests.approvals import a_run, listeners, runtime_of
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.db.helpers import member, person
from tests.link import holding


async def _ask(engine: AsyncEngine, redis: Redis, run_id: uuid.UUID, step: str = "post") -> ApprovalView:
    async with engine.begin() as conn:
        return (await ask_approval(conn, redis, run_id, step, f"{step.title()} it?")).approval


async def test_the_waiting_ones_are_listed_newest_first_and_only_ones_own(
    engine: AsyncEngine, redis: Redis, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    grace, eve = await member(engine, ada.org_id), await person(engine)
    run_id = await a_run(engine, ada, model="daily_sales")
    first, second = await _ask(engine, redis, run_id, "post"), await _ask(engine, redis, run_id, "send")
    for other in (grace, eve):
        await _ask(engine, redis, await a_run(engine, other))
    answered = await _ask(engine, redis, run_id, "pay")
    async with holding(redis, await runtime_of(engine, run_id)):
        res = await client.post(f"/v1/approvals/{answered.id}", json={"answer": "decline"}, headers=ada.headers)
    assert res.is_success
    listed = await client.get("/v1/approvals", headers=ada.headers)
    assert listed.status_code == 200
    assert listed.json() == [second.model_dump(mode="json"), first.model_dump(mode="json")]
    assert [a["model"] for a in listed.json()] == ["daily_sales", "daily_sales"]
    assert (await client.get("/v1/approvals")).json()["error"]["code"] == "E_UNAUTHORIZED"


async def test_the_first_answer_wins_and_is_handed_to_the_runtime_and_every_claude(
    engine: AsyncEngine, redis: Redis, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    run_id = await a_run(engine, ada)
    asked = await _ask(engine, redis, run_id)
    async with redis.pubsub() as pubsub, holding(redis, await runtime_of(engine, run_id)) as sent:
        await pubsub.subscribe(channel(ada.user_id))
        res = await client.post(f"/v1/approvals/{asked.id}", json={"answer": "approve"}, headers=ada.headers)
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
        message = message or await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
        handed = await sent()
    assert res.status_code == 200 and res.json() == {"id": str(asked.id), "answer": "approve"}
    assert message is not None and json.loads(message["data"]) == {"event": "answered", "data": res.json()}
    assert {k: handed[k] for k in ("type", "run_id", "answer")} == {
        "type": "continue",
        "run_id": str(run_id),
        "answer": {"approved": True},
    }
    async with engine.connect() as conn:
        row = (await conn.execute(select(Approval).where(Approval.id == asked.id))).one()
    assert row.answer == "approve" and row.answered_at is not None
    again = await client.post(f"/v1/approvals/{asked.id}", json={"answer": "decline"}, headers=ada.headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "E_CONFLICT"
    assert again.json()["error"]["answer"] == "approve"


async def test_two_claudes_answering_at_once_get_one_answer(
    engine: AsyncEngine, redis: Redis, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    run_id = await a_run(engine, ada)
    asked = await _ask(engine, redis, run_id)
    url = f"/v1/approvals/{asked.id}"
    async with holding(redis, await runtime_of(engine, run_id)):
        both = await asyncio.gather(
            client.post(url, json={"answer": "approve"}, headers=ada.headers),
            client.post(url, json={"answer": "decline"}, headers=ada.headers),
        )
    assert sorted(r.status_code for r in both) == [200, 409]


async def test_an_answer_while_the_runtime_is_away_is_refused_and_the_step_keeps_waiting(
    engine: AsyncEngine, redis: Redis, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    asked = await _ask(engine, redis, await a_run(engine, ada))
    res = await client.post(f"/v1/approvals/{asked.id}", json={"answer": "approve"}, headers=ada.headers)
    assert res.status_code == 503 and res.json()["error"]["reason"] == "runtime_offline"
    assert [a["id"] for a in (await client.get("/v1/approvals", headers=ada.headers)).json()] == [str(asked.id)]


async def test_only_ones_own_approval_is_answered_and_only_with_approve_or_decline(
    engine: AsyncEngine, redis: Redis, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    grace, eve = await member(engine, ada.org_id), await person(engine)
    asked = await _ask(engine, redis, await a_run(engine, ada))
    for who, approval_id in ((grace, asked.id), (eve, asked.id), (ada, uuid.uuid4())):
        res = await client.post(f"/v1/approvals/{approval_id}", json={"answer": "approve"}, headers=who.headers)
        assert res.status_code == 404 and res.json()["error"]["code"] == "E_NOT_FOUND"
    for body in ({"answer": "yes"}, {}):
        res = await client.post(f"/v1/approvals/{asked.id}", json=body, headers=ada.headers)
        assert res.status_code == 422 and res.json()["error"]["code"] == "E_INVALID"


@pytest.fixture
async def app(engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    made = create_app(PROVIDER_SETTINGS)
    async for _ in _client(made):
        yield made


async def test_the_stream_replays_the_waiting_then_sends_each_ask_and_answer_live(
    engine: AsyncEngine, redis: Redis, app: FastAPI, client: httpx.AsyncClient
) -> None:
    ada = await person(engine)
    run_id = await a_run(engine, ada)
    waiting = await _ask(engine, redis, run_id, "post")
    async with sse(app, "/v1/approvals/stream", ada.headers) as stream:
        assert stream.status == 200
        assert await stream.event() == f"event: approval\ndata: {waiting.model_dump_json()}\n\n"
        live = await _ask(engine, redis, run_id, "send")
        assert await stream.event() == f"event: approval\ndata: {live.model_dump_json()}\n\n"
        async with holding(redis, await runtime_of(engine, run_id)):
            await client.post(f"/v1/approvals/{live.id}", json={"answer": "decline"}, headers=ada.headers)
        answered = json.dumps({"id": str(live.id), "answer": "decline"}, separators=(",", ":"))
        assert await stream.event() == f"event: answered\ndata: {answered}\n\n"
        assert await listeners(redis, channel(ada.user_id), 1) == 1
    assert await listeners(redis, channel(ada.user_id), 0) == 0


async def test_the_stream_needs_a_token(app: FastAPI) -> None:
    async with sse(app, "/v1/approvals/stream", {"authorization": "Bearer nope"}) as stream:
        assert stream.status == 401
        assert json.loads(await stream.frame())["error"]["code"] == "E_UNAUTHORIZED"
