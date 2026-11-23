"""A bot's runs as the person sees them (ops/bots/service.py, runs.py, mend.py; docs/specs/bot-agent-loop.md, 2), with
the agent's turn faked at the service's boundary: a run is queued, runs and is listed; a bot has one live run; an
answer must fit the question; a wrong decision is corrected; a run is cancelled while it waits, while it is queued and
while it runs; and a bot's limits (runs a day, tokens a run) stop it saying so."""

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import runs
from glyphh_server.ops.bots.agent import run as agent_run
from glyphh_server.ops.bots.agent import session
from glyphh_server.ops.bots.agent.turn import Ended, Turn
from glyphh_server.ops.link.protocol import Call, Cancel, Continue
from tests.bots.agents import SESSION, play
from tests.bots.conftest import (
    BOTS,
    DECIDE,
    FIND,
    SEND,
    Served,
    answered,
    connected,
    inbox,
    made_bot,
    ran,
    run_of,
    serve,
)
from tests.bots.fakes import MAIL, FakePipedream
from tests.bots.remote import OnRrotor, left, out, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import Person

REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
ITEMS: dict[str, Any] = {"decision": "worth", "items": MAIL}
ASK: str = "ask_person"
ASKS: tuple[str, dict[str, Any]] = (ASK, {"question": "", **ITEMS})  # the person asked about the mail
GATE: str = "bot-inbox-cat-gate-worth"


async def post(s: Served, who: Person, path: str, body: Any = None) -> Any:
    return await s.http.post(path, json=body, headers=who.headers)


def held() -> tuple[Any, asyncio.Event, asyncio.Event]:
    """A go that says it has begun, then works until it is let go (or is cancelled)."""
    begun, let_go = asyncio.Event(), asyncio.Event()

    async def go(turn: Turn) -> Ended:
        begun.set()
        await let_go.wait()
        return Ended(text="Done at last.", session=SESSION, input_tokens=7, output_tokens=3)

    return go, begun, let_go


async def test_a_run_is_queued_runs_and_is_listed_with_what_it_said(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    served.agent.script = [play((FIND, {"q": "is:unread"}), text="Two letters: **Lunch on Friday?** and one of spam.")]
    res = await post(served, ana, f"/v1/bots/{bot['slug']}/runs", {"input": "Anything new?"})
    assert res.status_code == 202 and res.json()["status"] == "queued" and res.json()["bot_slug"] == "inbox-cat"
    await served.settled()
    run = await run_of(served, ana, res.json()["id"])
    assert (run["status"], run["error"], run["question"]) == ("done", "", None)
    assert run["output"].startswith("Two letters") and run["summary"] == "" and run["input"] == "Anything new?"
    assert run["started_at"] and run["finished_at"] and run["log"] == ["Find Email"]
    assert (run["input_tokens"], run["output_tokens"], run["own_key"]) == (1000, 200, False)
    assert run["cost_micros"] == 0 and run["runs_on"] is None  # inside the plan's allowance: nothing charged
    assert served.pd.runs[0]["configured_props"]["q"] == "is:unread"
    assert served.pd.runs[0]["external_user_id"] == f"org_{ana.org_id}"  # the tool ran as the org
    served.agent.script = [play(text="")]  # an agent that ends with no words
    silent = await ran(served, ana, bot["slug"], "Say nothing")
    assert (silent["status"], silent["output"]) == ("done", "")
    assert silent["summary"] == "It finished without saying anything."
    listed = (await served.http.get(f"/v1/bots/{bot['slug']}/runs", headers=ana.headers)).json()["runs"]
    assert [r["id"] for r in listed] == [silent["id"], run["id"]] and listed[0]["summary"] == silent["summary"]
    assert (await served.http.get(f"/v1/bot-runs/{uuid.uuid4()}", headers=ana.headers)).status_code == 404
    shown = (await served.http.get(f"/v1/bots/{bot['slug']}", headers=ana.headers)).json()
    assert shown["last_run"]["id"] == silent["id"] and shown["last_run"]["status"] == "done"


async def test_a_bot_has_one_live_run_and_an_answer_must_fit_its_question(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana, connections=[])
    served.agent.script = [play(ASKS)]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")
    assert run["status"] == "needs_input" and run["question"]["answer_with"] == "1=answer 2=skip"
    again = await post(served, ana, f"/v1/bots/{bot['slug']}/runs", {})
    assert again.status_code == 409 and again.json()["error"]["code"] == "E_CONFLICT"
    assert "answer it, or cancel it, first" in again.json()["error"]["message"]
    for wrong in ("1=maybe", "nonsense"):  # not an outcome, not an answer
        res = await post(served, ana, f"/v1/bot-runs/{run['id']}/answer", {"answer": wrong})
        assert res.status_code == 422 and res.json()["error"]["reason"] == "answer", wrong
    assert (await run_of(served, ana, run["id"]))["status"] == "needs_input"  # it keeps waiting
    waiting = (await served.http.get("/v1/bot-approvals", headers=ana.headers)).json()["runs"]
    assert [(w["id"], w["question"]["question"]) for w in waiting] == [(run["id"], "Worth answering?")]
    idle = await served.http.get(f"/v1/bots/{bot['slug']}/gates", headers=ana.headers)
    assert idle.status_code == 200  # a run that waits is not going: what its decisions learned can be read


async def test_an_approval_takes_yes_or_no_however_it_is_typed(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    served.agent.script = [play((SEND, REPLY)), play((SEND, REPLY), text="Sent.")]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    res = await post(served, ana, f"/v1/bot-runs/{run['id']}/answer", {"answer": "maybe"})
    assert res.status_code == 422 and res.json()["error"]["options"] == ["yes", "no"]
    assert (await post(served, ana, f"/v1/bot-runs/{run['id']}/answer", {"answer": 7})).status_code == 422
    done = await answered(served, ana, run["id"], [" YES "])
    assert done["status"] == "done" and len(served.pd.runs) == 1
    late = await post(served, ana, f"/v1/bot-runs/{run['id']}/answer", {"answer": "yes"})
    assert late.status_code == 409 and late.json()["error"]["message"] == "That run is not waiting on an answer."


async def test_an_answer_that_lost_the_race_to_another_is_refused(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = await made_bot(served, ana, connections=[])
    served.agent.script = [play(ASKS)]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")

    async def taken(*_: Any) -> bool:
        return False  # another answer carried it on first

    monkeypatch.setattr(runs, "queue", taken)
    res = await post(served, ana, f"/v1/bot-runs/{run['id']}/answer", {"answer": "1=answer 2=skip"})
    assert res.status_code == 409 and served.ada.outcomes(GATE) == []


async def test_a_wrong_decision_of_a_run_is_corrected_and_learned(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana, connections=[])
    one = {"decision": "worth", "items": [{"id": "m3", "subject": "Newsletter"}]}
    served.agent.script = [play((ASK, {"question": "", **one})), play(text="Nothing worth answering.")]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")
    done = await answered(served, ana, run["id"], "skip")
    assert done["status"] == "done" and done["data"]["worth"]["decisions"][0]["outcome"] == "skip"
    res = await post(served, ana, f"/v1/bot-runs/{run['id']}/wrong", {"outcome": "answer", "item": "m3"})
    assert res.status_code == 200, res.text
    assert (res.json()["said"], res.json()["now"]) == ("skip", "answer")
    assert served.ada.outcomes(GATE) == ["skip", "answer"]
    bad = await post(served, ana, f"/v1/bot-runs/{run['id']}/wrong", {"outcome": "maybe"})
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "wrong"
    gates = (await served.http.get(f"/v1/bots/{bot['slug']}/gates", headers=ana.headers)).json()["gates"]
    assert gates["worth"]["precedents"] == 2
    listed = (await served.http.get(f"/v1/bots/{bot['slug']}/decisions", headers=ana.headers)).json()["decisions"]
    assert [(d["outcome"], d["corrected"], d["now"]) for d in listed] == [("skip", "answer", "answer")]
    plain = await ran(served, ana, bot["slug"], "Hi")  # a run that decided nothing has nothing to correct
    none = await post(served, ana, f"/v1/bot-runs/{plain['id']}/wrong", {"outcome": "skip"})
    assert none.status_code == 422 and none.json()["error"]["reason"] == "run"
    assert "decided nothing with Ada" in none.json()["error"]["message"]


async def test_a_waiting_run_is_cancelled_and_is_not_the_one_carried_on(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    bot = await made_bot(served, ana, connections=[])
    served.agent.script = [play(ASKS)]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")
    store = session.Sessions(engine, ana.org_id, uuid.UUID(run["id"]))
    await store.append({"session_id": SESSION}, [{"type": "user", "uuid": "u-1"}])  # as its turn mirrored it
    res = await post(served, ana, f"/v1/bot-runs/{run['id']}/cancel")
    assert res.status_code == 200 and (res.json()["status"], res.json()["error"]) == ("failed", "cancelled")
    assert res.json()["summary"] == "Cancelled before it finished." and res.json()["question"] is None
    assert await store.load({"session_id": SESSION}) is None  # its session went with it
    for path, body in (("answer", {"answer": "1=answer 2=skip"}), ("cancel", None)):
        assert (await post(served, ana, f"/v1/bot-runs/{run['id']}/{path}", body)).status_code == 409
    nothing = await post(served, ana, f"/v1/bot-runs/{run['id']}/wrong", {"outcome": "skip"})
    assert nothing.status_code == 422 and served.ada.outcomes(GATE) == []  # asked, never answered: nothing decided
    assert (await ran(served, ana, bot["slug"], "Hi"))["status"] == "done"  # the bot is free again


async def test_a_run_that_is_going_is_stopped_by_cancelling_it(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    go, begun, _ = held()
    served.agent.script = [go]
    res = await post(served, ana, f"/v1/bots/{bot['slug']}/runs", {"input": "A long job"})
    await begun.wait()
    assert (await run_of(served, ana, res.json()["id"]))["status"] == "running"
    busy = await served.http.get(f"/v1/bots/{bot['slug']}/gates", headers=ana.headers)
    assert busy.status_code == 409 and "has a run going" in busy.json()["error"]["message"]
    turn = served.agent.turns[0]
    assert turn.folder.is_dir()  # the run's own folder, while its turn runs
    stopped = await post(served, ana, f"/v1/bot-runs/{res.json()['id']}/cancel")
    assert stopped.status_code == 200 and (stopped.json()["status"], stopped.json()["error"]) == ("failed", "cancelled")
    await served.settled()
    run = await run_of(served, ana, res.json()["id"])
    assert (run["status"], run["output"], run["summary"]) == ("failed", "", "Cancelled before it finished.")
    assert not turn.folder.exists() and run["finished_at"]
    assert (await ran(served, ana, bot["slug"], "Hi"))["status"] == "done"


async def test_a_run_still_queued_behind_another_is_cancelled_before_it_starts(
    engine: AsyncEngine, ana: Person
) -> None:
    async for s in serve(BOTS.model_copy(update={"bot_runs_at_once": 1}), FakePipedream()):
        first = await made_bot(s, ana, connections=[])
        second = await made_bot(s, ana, name="Second Cat", connections=[])
        go, begun, let_go = held()
        s.agent.script = [go]
        going = await post(s, ana, f"/v1/bots/{first['slug']}/runs", {"input": "A long job"})
        await begun.wait()
        waiting = await post(s, ana, f"/v1/bots/{second['slug']}/runs", {"input": "Next"})
        await asyncio.sleep(0.05)
        assert (await run_of(s, ana, waiting.json()["id"]))["status"] == "queued"  # no place free on this machine
        stopped = await post(s, ana, f"/v1/bot-runs/{waiting.json()['id']}/cancel")
        assert (stopped.json()["status"], stopped.json()["error"]) == ("failed", "cancelled")
        let_go.set()
        await s.settled()
        assert (await run_of(s, ana, going.json()["id"]))["output"] == "Done at last."
        assert (await run_of(s, ana, waiting.json()["id"]))["status"] == "failed" and len(s.agent.turns) == 1


async def test_a_run_cancelled_elsewhere_mid_go_keeps_its_tokens_only(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    bot = await made_bot(served, ana)

    async def go(turn: Turn) -> Ended:  # cancelled on another of the server's machines while this one's turn ran
        await runs.failed(engine, ana.org_id, uuid.UUID(turn.folder.name), "cancelled")
        return Ended(text="All done!", session=SESSION, input_tokens=900, output_tokens=100)

    served.agent.script = [go]
    run = await ran(served, ana, bot["slug"], "A long job")
    assert (run["status"], run["error"], run["output"]) == ("failed", "cancelled", "")
    assert (run["input_tokens"], run["output_tokens"]) == (900, 100)  # what it used is still on the meter


async def test_past_its_runs_a_day_a_bot_is_skipped_saying_so(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana, spec=inbox(limits={"runs_per_day": 2, "turns": 3, "seconds": 60}))
    for _ in range(2):
        assert (await ran(served, ana, bot["slug"], "Hi"))["status"] == "done"
    assert (served.agent.turns[0].turns, served.agent.turns[0].seconds) == (3, 60.0)
    res = await post(served, ana, f"/v1/bots/{bot['slug']}/runs", {"input": "Hi"})
    assert res.status_code == 202 and res.json()["status"] == "skipped"
    assert res.json()["summary"] == "It did not run: It has reached the most runs it may make in a day (2)."
    await served.settled()
    assert len(served.agent.turns) == 2 and (await run_of(served, ana, res.json()["id"]))["finished_at"]


async def test_a_run_over_its_tokens_fails_saying_so_at_its_end_or_before_it_is_carried_on(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    gmail = await connected(served, ana, allow=False)
    scopes = [{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}]
    bot = await made_bot(served, ana, spec=inbox(limits={"tokens": 1_500}), connections=scopes)
    served.agent.script = [play(text="A very long answer.", tokens=(1_400, 200))]
    over = await ran(served, ana, bot["slug"], "Everything, please")
    said = "It used more than a run may (1,500 tokens) and was stopped: ask for less at once."
    assert (over["status"], over["error"], over["output"]) == ("failed", said, "")
    assert over["summary"] == f"It failed: {said}" and (over["input_tokens"], over["output_tokens"]) == (1_400, 200)
    served.agent.script = [play((SEND, REPLY), tokens=(1_400, 200))]
    waits = await ran(served, ana, bot["slug"], "Reply to Grace")
    assert waits["status"] == "needs_input"  # it asked: the person's answer is what it waits on
    store = session.Sessions(engine, ana.org_id, uuid.UUID(waits["id"]))
    await store.append({"session_id": SESSION}, [{"type": "user", "uuid": "u-1"}])
    done = await answered(served, ana, waits["id"], "yes")
    assert (done["status"], done["error"]) == ("failed", said) and len(served.agent.turns) == 2  # no third go
    assert served.pd.runs == [] and await store.load({"session_id": SESSION}) is None
    assert agent_run.OVER.format(most=1_500) == said


async def test_a_waiting_run_that_had_decided_is_cancelled_and_its_decisions_stay(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    served.ada.cases[GATE].append(({}, "skip"))
    served.ada.rule[GATE] = lambda case: ("answer", 0.95)
    served.agent.script = [play((DECIDE, ITEMS), (SEND, REPLY))]
    run = await ran(served, ana, bot["slug"], "Answer what is worth it")
    assert run["status"] == "needs_input" and run["question"]["approval"]  # Ada decided; the send waits
    res = await post(served, ana, f"/v1/bot-runs/{run['id']}/cancel")
    assert (res.json()["status"], res.json()["error"]) == ("failed", "cancelled")
    listed = (await served.http.get(f"/v1/bots/{bot['slug']}/decisions", headers=ana.headers)).json()
    assert listed["total"] == 2 and {d["run_id"] for d in listed["decisions"]} == {run["id"]}
    fix = {"outcome": "skip", "gate": "worth", "item": "m2"}  # what it decided can still be corrected
    assert (await post(served, ana, f"/v1/bot-runs/{run['id']}/wrong", fix)).status_code == 200


async def test_a_bot_on_a_rrotor_has_its_runs_sent_answered_and_cancelled_there(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    who, rt, run = await out(on_rrotor, engine, plan="Team")
    assert run["status"] == "dispatched" and run["runs_on"] == str(rt.id)
    assert on_rrotor.s.agent.turns == [] and isinstance(on_rrotor.hub.last(), Call)  # no turn on the server
    assert (await on_rrotor.tool(run["id"], *ASKS))["ask"] is True  # the person is asked
    await on_rrotor.landed(rt, who, run["id"], left("needs_input", "Worth answering?"))  # the rrotor ends its turn
    waiting = await on_rrotor.run(who, run["id"])
    assert waiting["status"] == "needs_input" and waiting["question"]["decision"] == "worth"
    assert (await on_rrotor.answer(who, run["id"], "1=answer 2=skip"))["status"] == "dispatched"
    carried = on_rrotor.hub.last()
    assert isinstance(carried, Continue) and "Lunch on Friday? (id m1): answer" in str(carried.answer)
    stopped = await post(on_rrotor.s, who, f"/v1/bot-runs/{run['id']}/cancel")  # out there: stopped there too
    assert (stopped.json()["status"], stopped.json()["error"]) == ("failed", "cancelled")
    assert isinstance(on_rrotor.hub.last(), Cancel) and on_rrotor.hub.last().run_id == uuid.UUID(run["id"])
    again = await on_rrotor.start(who, said="more")
    other = {"decision": "worth", "items": [{"id": "m7", "subject": "Coffee?"}]}
    assert (await on_rrotor.tool(again["id"], ASK, {"question": "", **other}))["ask"] is True
    await on_rrotor.landed(rt, who, again["id"], left("needs_input", "Worth answering?"))
    sent = len(on_rrotor.hub.sent)
    ended = await post(on_rrotor.s, who, f"/v1/bot-runs/{again['id']}/cancel")  # while it waits on the person
    assert (ended.json()["status"], ended.json()["error"]) == ("failed", "cancelled")
    assert len(on_rrotor.hub.sent) == sent + 1 and isinstance(on_rrotor.hub.last(), Cancel)  # its wait there ends
    await on_rrotor.landed(rt, who, uuid.uuid4(), left("done", output="Whose is this?"))  # a result of no bot's run
    listed = (await on_rrotor.s.http.get("/v1/bots/inbox-cat/runs", headers=who.headers)).json()["runs"]
    assert [r["status"] for r in listed] == ["failed", "failed"]  # nothing of the bot's changed
