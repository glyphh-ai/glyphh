"""What a runtime reports over its link: each key's calls, counted once, and its precedents. A result goes to the run
it answers (none here: tests/bots/test_remote.py has them), an event or a deployed version is acked and kept nowhere;
a usage report that cannot be recorded closes the link unacked. A run's call, continue and cancel go down it."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import RuntimeKey
from glyphh_server.ops.link import calls, reports
from glyphh_server.ops.runtime_keys import key_hash
from tests.db.helpers import person
from tests.link import closed, linked, local_runtime, receive, runtime_row, self_runtime, server


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
    rt = await self_runtime(engine, ada)
    theirs = await self_runtime(engine, eve, "https://rrotor.eve.test")
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
    rt = await local_runtime(engine, ada)
    async with server() as srv, linked(srv, rt) as ws:
        await _send(ws, {"type": "usage", "id": "p1", "seq": 1, "keys": [], "precedents": 1_200})
        row = await runtime_row(engine, rt.id)
        assert (row.precedents, row.precedents_at is not None) == (1_200, True)
        await _send(ws, _usage("p2", 2))  # no reading yet: the last one stands
        await _send(ws, {"type": "usage", "id": "p3", "seq": 3, "precedents": 900})
        await ws.send_json({"type": "usage", "id": "p4", "seq": 4, "precedents": -1})  # unreadable: skipped
        await _send(ws, {"type": "usage", "id": "p5", "seq": 5, "keys": [], "precedents": 950})
    assert (await runtime_row(engine, rt.id)).precedents == 950


async def test_results_events_and_deploys_are_acked_and_kept_nowhere(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    sha = "0123456789abcdef0123456789abcdef01234567"
    owed = [
        {"type": "result", "id": "r1", "seq": 1, "run_id": str(uuid.uuid4()), "result": {"status": "done"}},
        {"type": "event", "id": "e1", "seq": 2, "program": "daily_sales", "kind": "fired", "data": {"n": 2}},
        {"type": "deployed", "id": "d1", "program": "daily_sales", "version": 2, "commit_sha": sha},
    ]
    async with server() as srv, linked(srv, rt) as ws:
        for message in owed:
            await _send(ws, message)
        await _send(ws, {"type": "usage", "id": "u1", "seq": 3, "precedents": 10})  # numbers skipped are fine
    row = await runtime_row(engine, rt.id)
    assert (row.seq, row.precedents) == (3, 10)


async def test_a_runs_call_continue_and_cancel_go_down_the_link(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    run_id = uuid.uuid4()
    async with server() as srv, linked(srv, rt) as ws:
        hub = srv.app.state.hub
        assert await calls.call(hub, rt.id, run_id, "glyphh_bot", "run", {"given": "hi"})
        sent = await receive(ws, "call")
        assert (sent["run_id"], sent["program"], sent["version"], sent["function"]) == (
            str(run_id),
            "glyphh_bot",
            None,
            "run",
        )
        assert sent["inputs"] == {"given": "hi"} and sent["caller"] == "routine"
        assert await calls.carry_on(hub, rt.id, run_id, "yes")
        assert (await receive(ws, "continue"))["answer"] == "yes"
        assert await calls.cancel(hub, rt.id, run_id)
        assert (await receive(ws, "cancel"))["run_id"] == str(run_id)


async def test_a_usage_report_that_cannot_be_recorded_closes_the_link_unacked(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_: object) -> None:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(reports, "apply_usage", broken)
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    async with server() as srv, linked(srv, rt) as ws:
        await ws.send_json({"type": "usage", "id": "u1", "seq": 1, "precedents": 5})
        assert await closed(ws) == (1011, "That message could not be recorded. Reconnect and replay it.")
    assert (await runtime_row(engine, rt.id)).seq == 0
