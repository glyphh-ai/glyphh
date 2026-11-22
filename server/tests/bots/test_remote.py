"""A bot's runs on the org's rrotor (docs/specs/bots.md, 9): sent there as a call of glyphh_bot (its package, state,
Ada key and tool address), dispatched until its result comes back; the result kept once (the bot's state with it,
the new tokens on the meter at the org's own key's rate); a question answered with `continue` while the rrotor
holds it, else a fresh call; cancelled there too; anything that keeps the call from going fails the run."""

import base64
import uuid
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, Invalid
from glyphh_server.models import Bot, BotRun
from glyphh_server.ops.bots import due
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.protocol import Call, Cancel, Continue
from tests.bots.conftest import Served, made_bot
from tests.bots.remote import OnRrotor, online, result, rrotor_fixture  # noqa: F401 (the fixture)
from tests.bots.test_schedules import _due, quiet  # noqa: F401 (quiet: no bot left due after a test)
from tests.db.helpers import Person, person
from tests.link import Rt, principal

ASK: dict[str, Any] = {"question": "Send the reply?", "options": ["yes", "no"], "step": "send", "approval": True}


async def _started(r: OnRrotor, engine: AsyncEngine) -> tuple[Person, Rt, dict[str, Any]]:
    ada = await person(engine)
    rt = await online(engine, ada)
    await made_bot(r.s, ada, runs_on=str(rt.id))
    run = await r.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "lunch"}, headers=ada.headers)
    assert run.status_code == 202, run.text
    return ada, rt, run.json()


async def _run(r: OnRrotor, who: Person, run_id: Any) -> dict[str, Any]:
    return dict((await r.s.http.get(f"/v1/bot-runs/{run_id}", headers=who.headers)).json())


async def _row(engine: AsyncEngine, run_id: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(select(BotRun).where(BotRun.id == uuid.UUID(str(run_id))))).one()


async def test_a_run_is_sent_to_its_rrotor_and_its_result_kept_once(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, run = await _started(on_rrotor, engine)
    assert run["status"] == "dispatched" and run["runs_on"] == str(rt.id) and run["kind"] == "bot"
    to, sent = on_rrotor.hub.sent[-1]
    assert to == rt.id and isinstance(sent, Call) and sent.run_id == uuid.UUID(run["id"])
    assert (sent.program, sent.function, sent.version) == ("glyphh_bot", "run", None)
    given = sent.inputs
    assert given["given"] == "lunch" and given["claude"] == "api" and given["state"] is None and "answer" not in given
    assert given["tool_url"] == f"https://api.glyphh.test/v1/bots/runs/{run['id']}/tool" and given["tool_token"]
    assert "bot.json" in given["package"] and given["ada_key"] and given["ada_base"].startswith("https://")
    tokens = {"input_tokens": 1000, "output_tokens": 200}
    state = base64.b64encode(b"runs.sqlite").decode()
    seq = await on_rrotor.landed(rt, ada, sent.run_id, result(output="Sent the reply.", tokens=tokens, state=state))
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["status"] == "done" and ended["output"] == "Sent the reply." and ended["own_key"] is True
    assert (ended["input_tokens"], ended["output_tokens"]) == (1000, 200) and ended["started_at"]
    async with engine.connect() as conn:
        assert (await conn.execute(select(Bot.state).where(Bot.id == (await _row(engine, run["id"])).bot_id))).scalar()
    await on_rrotor.landed(rt, ada, sent.run_id, result("failed", reason="late"), seq=seq)  # a replay: skipped
    assert (await _run(on_rrotor, ada, run["id"]))["status"] == "done"
    await on_rrotor.landed(rt, ada, uuid.uuid4(), result())  # no run of it: skipped
    assert len(on_rrotor.hub.sent) == 1


async def test_a_question_is_answered_on_the_rrotor_or_by_a_fresh_call(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _started(on_rrotor, engine)
    run_id = uuid.UUID(run["id"])
    await on_rrotor.landed(
        rt, ada, run_id, result("needs_input", tokens={"input_tokens": 100, "output_tokens": 10}, **ASK)
    )
    waiting = await _run(on_rrotor, ada, run_id)
    assert waiting["status"] == "needs_input" and waiting["question"]["options"] == ["yes", "no"]
    queue = (await on_rrotor.s.http.get("/v1/bot-approvals", headers=ada.headers)).json()["runs"]
    assert [(q["id"], q["kind"], q["runs_on"]) for q in queue] == [(str(run_id), "bot", str(rt.id))]
    res = await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "yes"}, headers=ada.headers)
    assert res.status_code == 202 and res.json()["status"] == "dispatched"
    assert isinstance(on_rrotor.hub.last(), Continue) and on_rrotor.hub.last().answer == "yes"
    gone = {"status": "failed", "step": "continue", "data": {"reason": "no such run", "code": "E_RUN_MISSING"}}
    await on_rrotor.landed(rt, ada, run_id, gone)  # the rrotor restarted: the answer goes as a call
    again = on_rrotor.hub.last()
    assert isinstance(again, Call) and again.inputs["answer"] == "yes" and "given" not in again.inputs
    await on_rrotor.landed(
        rt, ada, run_id, result("needs_input", tokens={"input_tokens": 50, "output_tokens": 5}, **ASK)
    )
    await on_rrotor.landed(rt, ada, run_id, {"status": "cancelled", "step": "wait", "data": {}})  # no news
    assert (await _row(engine, run_id)).remote["since"]
    await on_rrotor.landed(rt, ada, run_id, {"status": "expired", "step": "wait", "data": {}})
    assert (await _run(on_rrotor, ada, run_id))["status"] == "needs_input"  # still waits here
    await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "no"}, headers=ada.headers)
    fresh = on_rrotor.hub.last()
    assert isinstance(fresh, Call) and fresh.inputs["answer"] == "no"
    await on_rrotor.landed(rt, ada, run_id, result(output="Left it.", tokens={"input_tokens": 80, "output_tokens": 8}))
    ended = await _run(on_rrotor, ada, run_id)
    assert ended["status"] == "done" and (ended["input_tokens"], ended["output_tokens"]) == (230, 23)
    with pytest.raises(Conflict):  # answered already: it no longer waits
        stale = SimpleNamespace(**{**(await _row(engine, run_id))._asdict(), "status": "needs_input"})
        await on_rrotor.s.app.state.bots.remote.answer(principal(ada), stale, "yes")
    async with engine.begin() as conn:  # a rrotor that is not the org's
        await tenancy.enter(conn, ada.org_id)
        with pytest.raises(Invalid):
            await calls.linked(conn, uuid.uuid4())


async def test_a_run_out_on_the_rrotor_or_waiting_there_is_cancelled_there(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _started(on_rrotor, engine)
    res = await on_rrotor.s.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=ada.headers)
    assert res.json()["status"] == "failed" and res.json()["error"] == "cancelled"
    assert isinstance(on_rrotor.hub.last(), Cancel)
    for expired in (False, True):
        run = (await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
        await on_rrotor.landed(rt, ada, uuid.UUID(run["id"]), result("needs_input", **ASK))
        if expired:
            await on_rrotor.landed(rt, ada, uuid.UUID(run["id"]), {"status": "expired", "step": "wait", "data": {}})
        told = len(on_rrotor.hub.sent)
        res = await on_rrotor.s.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=ada.headers)
        assert res.status_code == 200, res.text
        assert len(on_rrotor.hub.sent) == told + (0 if expired else 1)


async def test_a_call_that_cannot_go_fails_its_run_saying_why(
    on_rrotor: OnRrotor, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    on_rrotor.hub.up = False  # the rrotor's link dropped just now
    ada, rt, run = await _started(on_rrotor, engine)
    shown = await _run(on_rrotor, ada, run["id"])
    assert shown["status"] == "failed" and "The bot's rrotor is not linked to Glyphh right now" in shown["error"]
    on_rrotor.hub.up = True
    monkeypatch.setattr(calls, "LINK_MAX", 1000)
    run = (await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    assert run["status"] == "failed" and "more than a rrotor's link takes" in run["error"]
    monkeypatch.undo()
    run = (await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    await on_rrotor.landed(rt, ada, uuid.UUID(run["id"]), result("needs_input", **ASK))
    on_rrotor.hub.up = False
    res = await on_rrotor.s.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": "yes"}, headers=ada.headers)
    assert res.json()["status"] == "failed" and "not linked" in res.json()["error"]
    on_rrotor.hub.up = True
    run = (await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    await on_rrotor.landed(rt, ada, uuid.UUID(run["id"]), result(state="not base64!"))
    shown = await _run(on_rrotor, ada, run["id"])
    assert shown["status"] == "failed" and shown["error"].startswith("The rrotor's result could not be kept")
    other = await online(engine, ada)
    run = (await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    await on_rrotor.landed(other, ada, uuid.UUID(run["id"]), result())  # not from its rrotor: skipped
    assert (await _run(on_rrotor, ada, run["id"]))["status"] == "dispatched"


async def test_a_rrotor_reaches_the_server_only_over_https(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await online(engine, ada)
    await made_bot(served, ada, runs_on=str(rt.id))
    run = (await served.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    assert run["status"] == "failed" and run["error"].startswith("A rrotor reaches this server only over https")


async def test_a_bots_schedule_sends_its_run_to_its_rrotor(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await online(engine, ada)
    await made_bot(on_rrotor.s, ada, runs_on=str(rt.id), schedule={"every": "hour"})
    await _due(engine, ada, timedelta(minutes=1))
    assert await due.fire(on_rrotor.s.app.state.bots) == 1
    assert isinstance(on_rrotor.hub.last(), Call) and on_rrotor.hub.sent[-1][0] == rt.id
