"""Runs over the link: a call down it, its results recorded once each, a step that needs approval waiting for the
person and their answer reaching the runtime, a call routed through Redis to the process holding the link, events
recorded and fired, deploys recorded, and a message that cannot be recorded closing the link unacked."""

import json
import uuid
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Approval, Deployment, ModelEvent, RoutineTrigger, Run
from glyphh_server.ops import vault
from glyphh_server.ops.approvals import channel
from glyphh_server.ops.link import inbound
from glyphh_server.ops.link.calls import send_call
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.routine_triggers import sealed_for
from tests.conftest import SETTINGS
from tests.db.helpers import Person, person
from tests.fakes import FakeRoutines
from tests.link import SHA2, Rt, a_model, closed, deploy, linked, local_runtime, receive, runtime_row, server

FIRE: str = "https://api.anthropic.com/v1/claude_code/routines/trig_01XYZ/fire"


async def _call(engine: AsyncEngine, hub: Hub, who: Person, rt: Rt, model_id: uuid.UUID) -> uuid.UUID:
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return await send_call(conn, hub, rt.id, model_id, None, "start", {"day": "2026-10-13"}, "claude")


async def _run(engine: AsyncEngine, run_id: uuid.UUID):  # type: ignore[no-untyped-def]
    async with engine.connect() as conn:
        return (await conn.execute(select(Run).where(Run.id == run_id))).one()


def _result(run_id: uuid.UUID, seq: int, status: str, seconds: int, **more: Any) -> dict[str, Any]:
    outcome = {"status": status, **more}
    return {"type": "result", "id": f"r{seq}", "seq": seq, "run_id": str(run_id), "result": outcome, "seconds": seconds}


async def _approvals(engine: AsyncEngine, run_id: uuid.UUID) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(select(func.count()).where(Approval.run_id == run_id))).scalar_one()


async def test_a_call_its_approval_the_answer_and_the_result_are_each_recorded_once(
    engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    model_id, v1, _ = await a_model(engine, ada)
    await deploy(engine, rt.id, v1)
    async with server() as srv, linked(srv, rt) as ws, redis.pubsub() as person_channel:
        await person_channel.subscribe(channel(ada.user_id))
        run_id = await _call(engine, srv.app.state.hub, ada, rt, model_id)
        call = await receive(ws, "call")
        assert {k: v for k, v in call.items() if k != "id"} == {
            "type": "call",
            "run_id": str(run_id),
            "model": "daily_sales",
            "version": 1,
            "function": "start",
            "inputs": {"day": "2026-10-13"},
            "caller": "claude",
            "clearance": 1.0,
        }
        assert (await _run(engine, run_id)).status == "running"
        asking = _result(run_id, 1, "needs_approval", 3, step="write", prompt="Write Monday's total?")
        await ws.send_json(asking)
        assert (await receive(ws, "ack"))["of"] == "r1"
        run = await _run(engine, run_id)
        assert (run.status, run.seconds, run.ended_at) == ("needs_approval", 3, None)
        heard = await person_channel.get_message(ignore_subscribe_messages=True, timeout=5)
        heard = heard or await person_channel.get_message(ignore_subscribe_messages=True, timeout=5)
        asked = json.loads(heard["data"])["data"]
        assert (asked["model"], asked["step"], asked["prompt"]) == ("daily_sales", "write", "Write Monday's total?")
        res = await srv.http.post(f"/v1/approvals/{asked['id']}", json={"answer": "approve"}, headers=ada.headers)
        assert res.status_code == 200, res.text
        cont = await receive(ws, "continue")
        assert (cont["run_id"], cont["answer"]) == (str(run_id), {"approved": True})
        assert (await _run(engine, run_id)).status == "running"
        await ws.send_json(_result(run_id, 2, "done", 5, data={"total": 42}))
        assert (await receive(ws, "ack"))["of"] == "r2"
        await ws.send_json(asking)  # a replay after a reconnect: acked, not applied again
        assert (await receive(ws, "ack"))["of"] == "r1"
    run = await _run(engine, run_id)
    assert (run.status, run.seconds) == ("done", 5) and run.ended_at is not None
    assert await _approvals(engine, run_id) == 1
    assert (await runtime_row(engine, rt.id)).seq == 2


async def test_a_call_made_on_another_process_reaches_the_link_through_redis(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    model_id, v1, _ = await a_model(engine, ada)
    await deploy(engine, rt.id, v1)
    async with server() as holder, server() as other, linked(holder, rt) as ws:
        assert rt.id not in other.app.state.hub.links
        run_id = await _call(engine, other.app.state.hub, ada, rt, model_id)
        assert (await receive(ws, "call"))["run_id"] == str(run_id)
        await ws.send_json(_result(run_id, 1, "failed", 1, step="load", data={"reason": "no profile"}))
        assert (await receive(ws, "ack"))["of"] == "r1"
    run = await _run(engine, run_id)
    assert run.status == "failed" and run.ended_at is not None


async def test_a_result_for_a_run_it_does_not_have_is_acked_and_skipped(engine: AsyncEngine) -> None:
    ada, eve = await person(engine), await person(engine)
    rt = await local_runtime(engine, ada)
    model_id, v1, _ = await a_model(engine, eve)
    eves = await local_runtime(engine, eve)
    await deploy(engine, eves.id, v1)
    async with server() as srv, linked(srv, eves) as eve_ws, linked(srv, rt) as ws:
        eve_run = await _call(engine, srv.app.state.hub, eve, eves, model_id)
        await receive(eve_ws, "call")
        for seq, run_id in enumerate((uuid.uuid4(), eve_run), start=1):
            await ws.send_json(_result(run_id, seq, "done", 1))
            assert (await receive(ws, "ack"))["of"] == f"r{seq}"
    assert (await _run(engine, eve_run)).status == "running"


async def test_a_message_that_cannot_be_recorded_closes_the_link_unacked(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*_: object) -> None:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(inbound, "apply_result", broken)
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    async with server() as srv, linked(srv, rt) as ws:
        await ws.send_json(_result(uuid.uuid4(), 1, "done", 1))
        assert await closed(ws) == (1011, "That message could not be recorded. Reconnect and replay it.")
    assert (await runtime_row(engine, rt.id)).seq == 0


async def _trigger(engine: AsyncEngine, who: Person, model_id: uuid.UUID | None) -> uuid.UUID:
    key = vault.load_key(SETTINGS)
    sealed = vault.seal(key, "routine-token", sealed_for(who.user_id, FIRE))
    values = {"user_id": who.user_id, "name": "Sales", "fire_url": FIRE, "token_enc": sealed, "model_id": model_id}
    async with engine.begin() as conn:
        return (await conn.execute(insert(RoutineTrigger).values(values).returning(RoutineTrigger.id))).scalar_one()


async def _events(engine: AsyncEngine, model_id: uuid.UUID) -> list[tuple[object, ...]]:
    async with engine.connect() as conn:
        rows = await conn.execute(select(ModelEvent).where(ModelEvent.model_id == model_id))
        return sorted((r.kind, r.routine_trigger_id, r.session_url) for r in rows)


async def test_events_are_recorded_and_fire_only_the_owners_trigger(engine: AsyncEngine) -> None:
    ada, eve = await person(engine, "Pro"), await person(engine, "Pro")
    rt = await local_runtime(engine, ada)
    model_id, _, _ = await a_model(engine, ada)
    mine, any_model = await _trigger(engine, ada, model_id), await _trigger(engine, ada, None)
    eves = await _trigger(engine, eve, None)
    fake = FakeRoutines()
    events = [
        ("plain", None),
        ("fired", mine),
        ("any", any_model),
        ("not-yours", eves),
        ("unknown", uuid.uuid4()),
    ]
    async with server(routines=fake) as srv, linked(srv, rt) as ws:
        for seq, (kind, trigger) in enumerate(events, start=1):
            if kind == "any":
                fake.reply = httpx.Response(500, text="down")
            message = {"type": "event", "id": f"e{seq}", "seq": seq, "model": "daily_sales", "kind": kind}
            await ws.send_json({**message, "data": {"n": seq}, "trigger": str(trigger) if trigger else None})
            assert (await receive(ws, "ack"))["of"] == f"e{seq}"
        await ws.send_json({"type": "event", "id": "lost", "seq": 9, "model": "nobody", "kind": "x"})
        assert (await receive(ws, "ack"))["of"] == "lost"
    session = "https://claude.ai/code/session_fake"
    assert await _events(engine, model_id) == sorted(
        [
            ("plain", None, None),
            ("fired", mine, session),
            ("any", None, None),
            ("not-yours", None, None),
            ("unknown", None, None),
        ]
    )
    assert len(fake.calls) == 2
    assert json.loads(json.loads(fake.calls[0].content)["text"]) == {
        "model": "daily_sales",
        "event": "fired",
        "data": {"n": 2},
    }


async def test_a_deployed_version_becomes_the_active_one_on_that_runtime(engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await local_runtime(engine, ada)
    _, v1, v2 = await a_model(engine, ada)
    await deploy(engine, rt.id, v1)
    deployed = {"type": "deployed", "id": "d1", "model": "daily_sales", "version": 2, "commit_sha": SHA2}
    async with server() as srv, linked(srv, rt) as ws:
        for message in (deployed, {**deployed, "id": "d2"}, {**deployed, "id": "d3", "version": 7}):
            await ws.send_json(message)
            assert (await receive(ws, "ack"))["of"] == message["id"]
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Deployment.model_version_id, Deployment.active).where(Deployment.rrotor_id == rt.id)
        )
        assert dict(rows.all()) == {v1: False, v2: True}
