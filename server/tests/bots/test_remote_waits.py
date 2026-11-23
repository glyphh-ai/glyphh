"""A bot's run on a rrotor that waits on the person (docs/specs/bot-agent-loop.md, 6.2): the question is the server's
own (asked at its desk) or the rrotor's about a file's change; the answer goes as `continue` while the rrotor still
holds the run (14 minutes), else as a fresh call that resumes the session the machine kept; a `continue` the rrotor
has no run for goes as a fresh call too; the run's tokens are counted once through all of it; cancelled, the run is
ended here and the rrotor told; and the orchestrator's run waits again when the bot it asked asks again."""

import uuid
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Conflict
from glyphh_server.models import BotRun
from glyphh_server.ops.bots import runs
from glyphh_server.ops.link.protocol import Call, Cancel, Continue
from tests.bots.agents import play
from tests.bots.conftest import SEND, connected, made_bot
from tests.bots.remote import EXPIRED, GONE, OnRrotor, left, online, out, row, rrotor_fixture  # noqa: F401
from tests.db.helpers import Person, person
from tests.link import Rt, principal

WRITE: dict[str, str] = {"action": "write", "path": "/Users/ana/Notes/a.md", "name": "Notes/a.md"}
REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
YES: str = "The person said yes to that. Do it now, exactly as you asked."


def _asks(tokens: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """The rrotor's own question, about a file's change."""
    return left("needs_input", "Write Notes/a.md?", tokens, options=["yes", "no"], approval=True, file=WRITE)


async def _waiting(r: OnRrotor, engine: AsyncEngine, tokens: tuple[int, int] = (0, 0)) -> tuple[Person, Rt, str]:
    ada, rt, run = await out(r, engine, plan="Enterprise")
    await r.landed(rt, ada, run["id"], _asks(tokens))
    return ada, rt, run["id"]


async def test_an_answer_goes_as_continue_while_the_rrotor_holds_the_run(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run_id = await _waiting(on_rrotor, engine)
    waiting = await on_rrotor.run(ada, run_id)
    assert waiting["status"] == "needs_input" and waiting["summary"] == "It is waiting on your answer."
    bad = await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "maybe"}, headers=ada.headers)
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "answer"  # it keeps waiting
    for other in ({"status": "cancelled", "step": "wait", "data": {}}, left(output="Done anyway.")):
        await on_rrotor.landed(rt, ada, run_id, other)  # while it waits here, only its wait expiring is news
    assert (await on_rrotor.run(ada, run_id))["status"] == "needs_input" and (await row(engine, run_id)).remote["since"]
    assert (await on_rrotor.answer(ada, run_id, "yes"))["status"] == "dispatched"
    to, carried = on_rrotor.hub.sent[-1]
    assert to == rt.id and isinstance(carried, Continue) and carried.run_id == uuid.UUID(run_id)
    assert carried.answer == YES and (await on_rrotor.run(ada, run_id))["question"] is None
    again = await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "yes"}, headers=ada.headers)
    assert again.status_code == 409  # answered already: it no longer waits
    with pytest.raises(Conflict):  # nor for an answer that raced the first
        stale = SimpleNamespace(**{**(await row(engine, run_id))._asdict(), "status": "needs_input"})
        await on_rrotor.s.app.state.bots.remote.answer(principal(ada), stale, "yes")
    await on_rrotor.landed(rt, ada, run_id, left(output="Wrote it."))
    assert (await on_rrotor.run(ada, run_id))["output"] == "Wrote it."


@pytest.mark.parametrize("how", ["expired", "late"])
async def test_an_answer_past_the_rrotors_wait_goes_as_a_fresh_call_that_resumes(
    on_rrotor: OnRrotor, engine: AsyncEngine, how: str
) -> None:
    ada, rt, run_id = await _waiting(on_rrotor, engine)
    first = on_rrotor.call()
    if how == "expired":  # the rrotor said its wait ran out
        await on_rrotor.landed(rt, ada, run_id, EXPIRED)
        assert (await on_rrotor.run(ada, run_id))["status"] == "needs_input"  # it still waits here
    else:  # it has waited 15 minutes: the rrotor holds a run 15, so past 14 the answer goes as a call
        since = (runs.now() - timedelta(minutes=15)).isoformat()
        async with engine.begin() as conn:
            waited = {**(await row(engine, run_id)).remote, "since": since}
            await conn.execute(update(BotRun).where(BotRun.id == uuid.UUID(run_id)).values(remote=waited))
    assert (await on_rrotor.answer(ada, run_id, "yes"))["status"] == "dispatched"
    fresh = on_rrotor.hub.last()
    assert isinstance(fresh, Call) and fresh.run_id == uuid.UUID(run_id) and fresh.function == "agent"
    assert fresh.inputs["resume"] is True and fresh.inputs["message"] == YES
    assert fresh.inputs["tool_url"] == first.inputs["tool_url"]  # the rrotor finds the run it kept by it
    assert fresh.inputs["system"] == first.inputs["system"] and fresh.inputs["tools"] == first.inputs["tools"]
    await on_rrotor.landed(rt, ada, run_id, left(output="Wrote it."))
    assert (await on_rrotor.run(ada, run_id))["status"] == "done"


async def test_a_continue_the_rrotor_has_no_run_for_goes_as_a_fresh_call(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run_id = await _waiting(on_rrotor, engine)
    await on_rrotor.answer(ada, run_id, "no")
    assert isinstance(on_rrotor.hub.last(), Continue)
    await on_rrotor.landed(rt, ada, run_id, GONE)  # the rrotor restarted: the answer goes as a call
    again = on_rrotor.hub.last()
    assert isinstance(again, Call) and again.inputs["resume"] is True
    assert again.inputs["message"].startswith("The person said no to that.")
    assert (await on_rrotor.run(ada, run_id))["status"] == "dispatched"
    await on_rrotor.landed(rt, ada, run_id, left(output="Left it."))
    assert (await on_rrotor.run(ada, run_id))["output"] == "Left it."


@pytest.mark.parametrize("expired", [False, True])
async def test_an_answer_that_cannot_reach_the_rrotor_fails_the_run_saying_why(
    on_rrotor: OnRrotor, engine: AsyncEngine, expired: bool
) -> None:
    ada, rt, run_id = await _waiting(on_rrotor, engine)
    if expired:
        await on_rrotor.landed(rt, ada, run_id, EXPIRED)
    on_rrotor.hub.up = False  # the rrotor's link dropped while the run waited
    ended = await on_rrotor.answer(ada, run_id, "yes")
    assert isinstance(on_rrotor.hub.last(), Call if expired else Continue)
    assert ended["status"] == "failed" and "The bot's rrotor is not linked to Glyphh right now" in ended["error"]
    assert ended["question"] is None


async def test_a_runs_tokens_are_counted_once_through_every_call_of_it(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run_id = await _waiting(on_rrotor, engine, tokens=(100, 10))
    await on_rrotor.answer(ada, run_id, "yes")
    await on_rrotor.landed(rt, ada, run_id, _asks((150, 15)))  # the run's total so far, after a `continue`
    assert _spent(await on_rrotor.run(ada, run_id)) == (150, 15)
    await on_rrotor.landed(rt, ada, run_id, EXPIRED)
    await on_rrotor.answer(ada, run_id, "yes")
    # a fresh call resumes the session the rrotor kept, and its count with it: still the run's total so far
    await on_rrotor.landed(rt, ada, run_id, _asks((230, 23)))
    assert _spent(await on_rrotor.run(ada, run_id)) == (230, 23)
    await on_rrotor.landed(rt, ada, run_id, EXPIRED)
    await on_rrotor.answer(ada, run_id, "yes")
    # a rrotor that lost the session begins the run again, from none: everything it then says is new
    await on_rrotor.landed(rt, ada, run_id, _asks((80, 8)))
    assert _spent(await on_rrotor.run(ada, run_id)) == (310, 31)
    await on_rrotor.answer(ada, run_id, "yes")
    await on_rrotor.landed(rt, ada, run_id, left(output="Wrote it.", tokens=(120, 12)))
    ended = await on_rrotor.run(ada, run_id)
    assert ended["status"] == "done" and _spent(ended) == (350, 35)


def _spent(run: dict[str, Any]) -> tuple[int, int]:
    return run["input_tokens"], run["output_tokens"]


async def test_a_run_out_on_the_rrotor_or_waiting_there_is_cancelled_there(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await out(on_rrotor, engine, plan="Enterprise")
    res = await on_rrotor.s.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=ada.headers)
    assert res.json()["status"] == "failed" and res.json()["error"] == "cancelled"
    to, told = on_rrotor.hub.sent[-1]
    assert to == rt.id and isinstance(told, Cancel) and told.run_id == uuid.UUID(run["id"])
    await on_rrotor.landed(rt, ada, run["id"], left(output="Too late."))  # it has ended here: skipped
    assert (await on_rrotor.run(ada, run["id"]))["output"] == ""
    for expired in (False, True):  # a waiting run: the rrotor is told while it still holds the wait
        run = await on_rrotor.start(ada)
        await on_rrotor.landed(rt, ada, run["id"], _asks())
        if expired:
            await on_rrotor.landed(rt, ada, run["id"], EXPIRED)
        told = len(on_rrotor.hub.sent)
        res = await on_rrotor.s.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=ada.headers)
        assert res.status_code == 200 and res.json()["error"] == "cancelled", res.text
        assert len(on_rrotor.hub.sent) == told + (0 if expired else 1)
        assert expired or isinstance(on_rrotor.hub.last(), Cancel)


async def test_the_orchestrator_on_a_rrotor_waits_again_when_the_bot_it_asked_asks_again(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    rt = await online(engine, ada)
    gmail = await connected(on_rrotor.s, ada, allow=False)
    await made_bot(on_rrotor.s, ada, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    moved = await on_rrotor.s.http.patch("/v1/bots/orchestrator", json={"runs_on": str(rt.id)}, headers=ada.headers)
    assert moved.status_code == 200, moved.text
    everyone = {**REPLY, "to": ["everyone@navy.test"]}
    on_rrotor.s.agent.script = [play((SEND, REPLY)), play((SEND, everyone)), play((SEND, everyone), text="Sent.")]
    run = await on_rrotor.start(ada, "orchestrator", "Reply to Grace")
    sent = on_rrotor.call()
    assert {"list_bots", "ask_bot"} <= {t["name"] for t in sent.inputs["tools"]}
    assert sent.inputs["limits"]["seconds"] == 900
    asked = await on_rrotor.tool(run["id"], "ask_bot", {"bot": "Inbox Cat", "task": "Reply to Grace"})
    assert asked == {"ask": True, "question": "Inbox Cat asks: Send Email in Gmail?"}
    await on_rrotor.landed(rt, ada, run["id"], left("needs_input", asked["question"]))
    waiting = await on_rrotor.run(ada, run["id"])
    assert waiting["status"] == "needs_input" and "grace@navy.test" in waiting["question"]["detail"]
    told = len(on_rrotor.hub.sent)
    again = await on_rrotor.answer(ada, run["id"], "yes")  # the bot carries on, and asks about another call
    assert again["status"] == "needs_input" and "everyone@navy.test" in again["question"]["detail"]
    assert len(on_rrotor.hub.sent) == told  # nothing went to the rrotor: its run still waits there
    assert (await on_rrotor.answer(ada, run["id"], "yes"))["status"] == "dispatched"
    carried = on_rrotor.hub.last()
    assert isinstance(carried, Continue) and carried.answer.startswith("Inbox Cat finished. Its answer:\n\nSent.")
    assert [p["configured_props"]["to"] for p in on_rrotor.s.pd.runs] == [["everyone@navy.test"]]
