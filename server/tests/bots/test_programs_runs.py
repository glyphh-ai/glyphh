"""A program run walked by the server (docs/specs/programs.md, 2 and 4): a tool step as its bot's call, a branch, the
person asked, a bot's run waited for and its question carried to the person, an approval before an action, each
step a line of the run's audit trail naming the bot that did it and the person who started or answered it."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import orchestrator
from tests.bots.agents import fails, play
from tests.bots.conftest import ASK, Served, made_bot
from tests.bots.fakes import MAIL
from tests.bots.programs import FIND_STEP, SEND_STEP, answered, made, ran, trail
from tests.db.helpers import Person

WALK: list[dict[str, Any]] = [
    {**FIND_STEP, "next": "which"},
    {"id": "which", "kind": "branch", "on": "{input}", "next": {"lunch": "ask", "else": None}},
    {"id": "ask", "kind": "ask", "question": "Reply to {input}?", "options": ["Yes", "No"],
     "next": {"Yes": "write", "else": None}},
    {"id": "write", "kind": "bot", "task": "Write a reply about {input}", "next": None},
]  # fmt: skip


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "EVERY", 0.01)  # how often a bot step looks at the bot's run


async def test_a_run_walks_its_steps_and_keeps_its_trail(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    await made(served, ana, WALK)
    waits = await ran(served, ana)
    assert waits["status"] == "needs_input" and waits["at"] == "ask" and waits["trigger"] == "person"
    assert waits["question"] == {"question": "Reply to lunch?", "options": ["Yes", "No"], "approval": False,
                                 "kind": "ask", "step": "ask"}  # fmt: skip
    assert waits["outputs"] == {"input": "lunch", "find": MAIL, "which": "lunch"}
    assert served.pd.runs[-1]["configured_props"]["q"] == "lunch"
    done = await answered(served, ana, waits["id"], "Yes")
    assert done["status"] == "done" and done["outputs"]["write"] == "Hello! I answer the mail worth answering."
    assert "_child" not in done["outputs"] and done["question"] is None and done["finished_at"]
    assert await trail(served, ana, done["id"]) == [
        ("started", "", None, "Ada Lovelace", True),
        ("step", "find", "inbox-cat", None, True),
        ("step", "which", None, None, True),
        ("asked", "ask", None, None, True),
        ("answered", "ask", None, "Ada Lovelace", True),
        ("step", "write", "inbox-cat", None, True),
        ("done", "", None, None, True),
    ]
    assert await trail(served, ana, done["id"], after=10**9) == []
    shown = (await served.http.get("/v1/programs/mail-round", headers=ana.headers)).json()
    assert shown["last_run"]["id"] == done["id"] and shown["last_run"]["status"] == "done"
    runs = (await served.http.get("/v1/programs/mail-round/runs", headers=ana.headers)).json()["runs"]
    assert [r["id"] for r in runs] == [done["id"]]


async def test_an_answer_can_end_the_run(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    await made(served, ana, WALK)
    waits = await ran(served, ana)
    over = await answered(served, ana, waits["id"], "No")
    assert over["status"] == "done" and over["outputs"]["ask"] == "No"
    assert (await ran(served, ana, said="dinner"))["status"] == "done"  # the branch's else: the end
    res = await served.http.post(f"/v1/program-runs/{waits['id']}/answer", json={"answer": "Yes"}, headers=ana.headers)
    assert res.status_code == 409


async def test_an_action_waits_for_the_persons_yes(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    conn = bot["connections"][0]["connection_id"]
    modes = {"permissions": {"gmail-send-email": "ask"}}
    assert (await served.http.put(f"/v1/connections/{conn}/permissions", json=modes, headers=ana.headers)).is_success
    await made(served, ana, [{**FIND_STEP, "next": "send"}, SEND_STEP])
    waits = await ran(served, ana)
    assert waits["question"]["kind"] == "approval" and waits["question"]["approval"] is True
    assert len(served.pd.runs) == 1  # not sent yet
    done = await answered(served, ana, waits["id"], "yes")
    assert done["status"] == "done" and served.pd.runs[-1]["configured_props"]["subject"] == "Re: "
    assert done["outputs"]["send"] == {"id": "msg_1"}
    again = await ran(served, ana)
    said_no = await answered(served, ana, again["id"], "no")
    assert said_no["status"] == "failed" and said_no["error"].startswith("Stopped: the person said no to ")
    assert (await trail(served, ana, again["id"]))[-2:] == [
        ("answered", "send", None, "Ada Lovelace", True),
        ("failed", "", None, None, False),
    ]


async def test_a_bots_question_goes_to_the_person_and_the_program_carries_on(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    await made(served, ana, [{"id": "write", "kind": "bot", "task": "Plan {input}", "next": None}])
    served.agent.script = [play((ASK, {"question": "Which day?", "options": ["Mon", "Fri"]})), play(text="Friday.")]
    waits = await ran(served, ana)
    assert waits["status"] == "needs_input" and waits["question"]["question"] == "Inbox Cat asks: Which day?"
    assert waits["question"]["kind"] == "bot" and waits["question"]["options"] == ["Mon", "Fri"]
    done = await answered(served, ana, waits["id"], "Fri")
    assert done["status"] == "done" and done["outputs"]["write"] == "Friday."


async def test_a_step_that_fails_ends_the_run_saying_why(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    await made(served, ana, [{"id": "write", "kind": "bot", "task": "Plan", "next": None}])
    served.agent.script = [fails("The model is busy.")]
    failed = await ran(served, ana)
    assert failed["status"] == "failed" and failed["error"].startswith("Inbox Cat could not do it: ")
    cases: list[tuple[list[dict[str, Any]], str]] = [
        ([{**FIND_STEP, "tool": "slack-send-message"}], "Inbox Cat has no tool slack-send-message"),
        ([{**FIND_STEP, "tool": "ask_person"}], "ask_person is the bot's own way to ask: use an ask step."),
    ]
    for flow, said in cases:
        await served.http.patch("/v1/programs/mail-round", json={"flow": flow}, headers=ana.headers)
        failed = await ran(served, ana)
        assert failed["status"] == "failed" and failed["error"].startswith(said), failed
    served.pd.fail_run = True
    await served.http.patch("/v1/programs/mail-round", json={"flow": [FIND_STEP]}, headers=ana.headers)
    failed = await ran(served, ana)
    assert failed["status"] == "failed" and "token was revoked" in failed["error"]
    assert (await trail(served, ana, failed["id"]))[-2] == ("step", "find", "inbox-cat", None, False)


async def test_a_program_with_no_bot_cannot_do_a_bots_step(served: Served, ana: Person) -> None:
    await made(served, ana, [FIND_STEP], bot=None)
    failed = await ran(served, ana)
    assert (
        failed["error"] == "find: this program has no bot to do it: choose the program's bot, or name one on the step."
    )


async def test_a_run_is_refused_while_it_cannot_run(served: Served, ana: Person, engine: AsyncEngine) -> None:
    await made(served, ana, [{"id": "a", "kind": "ask"}], bot=None)
    res = await served.http.post("/v1/programs/mail-round/runs", json={}, headers=ana.headers)
    assert res.status_code == 422 and res.json()["error"]["problems"] == ["a: a ask step needs its question"]
    await served.http.patch("/v1/programs/mail-round", json={"flow": []}, headers=ana.headers)
    res = await served.http.post("/v1/programs/mail-round/runs", json={}, headers=ana.headers)
    assert res.status_code == 422 and res.json()["error"]["message"] == "Mail Round has no steps yet."
    flow = [{"id": "a", "kind": "ask", "question": "?", "options": ["Go"], "next": None}]
    await served.http.patch("/v1/programs/mail-round", json={"flow": flow}, headers=ana.headers)
    waits = await ran(served, ana)
    res = await served.http.post("/v1/programs/mail-round/runs", json={}, headers=ana.headers)
    assert res.status_code == 409 and "already running" in res.json()["error"]["message"]
    gone = [{"id": "b", "kind": "ask", "question": "?"}]
    await served.http.patch("/v1/programs/mail-round", json={"flow": gone}, headers=ana.headers)
    over = await answered(served, ana, waits["id"], "Go")  # its step went: the answer still ends it
    assert over["status"] == "done"
