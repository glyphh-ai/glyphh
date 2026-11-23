"""A bot's run is one agent turn (docs/specs/bot-agent-loop.md): a greeting is answered and nothing runs; a task uses
the bot's tools, Ada answers what the person decided before and, as its instructions say, the bot asks the person
about what Ada is not sure of; an action waits for their yes, and the run ends on the bot's own words, its tokens on
the meter."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import orchestrator
from tests.bots.agents import fails, play
from tests.bots.conftest import DECIDE, FIND, SEND, Served, answered, connected, made_bot, ran, run_of
from tests.bots.fakes import MAIL
from tests.db.helpers import Person, person

REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
ITEMS: dict[str, Any] = {"decision": "worth", "items": MAIL}
GATE: str = "bot-inbox-cat-gate-worth"


def sure_of_spam(s: Served) -> None:
    """Ada knows `You won!` is to skip, and is not sure of anything else."""
    s.ada.cases[GATE].append(({}, "skip"))  # it decides alone once it holds a precedent
    s.ada.rule[GATE] = lambda case: ("skip", 0.95) if "won" in case["m"]["s"]["subject"] else ("answer", 0.4)


async def test_a_greeting_is_answered_and_nothing_runs(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    run = await ran(served, ana, bot["slug"], "Hi there")
    assert run["status"] == "done" and run["output"].startswith("Hello!")
    assert run["steps"] == [] and run["summary"] == "" and run["hint"] == ""
    assert served.pd.runs == []  # no tool ran: nothing was searched for "Hi there"
    turn = served.agent.turns[0]
    assert turn.message == "Hi there" and "You are Inbox Cat" in turn.system and "Worth answering?" in turn.system
    assert sorted(t.name for t in turn.tools) == ["ask_person", DECIDE, FIND, SEND]
    assert turn.skills == ["notes:replies"] and turn.session == ""
    assert (run["input_tokens"], run["output_tokens"]) == (1000, 200)


async def test_a_run_with_nothing_said_is_given_the_standing_task(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    await ran(served, ana, bot["slug"])
    assert served.agent.turns[0].message == "Answer the mail worth answering."


async def test_the_bot_asks_ada_and_then_the_person_about_what_ada_is_not_sure_of(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-find-email"]}])
    sure_of_spam(served)
    unsure = {"question": "", "decision": "worth", "items": MAIL[:1]}
    first = play((FIND, {"q": "is:unread"}), (DECIDE, ITEMS), ("ask_person", unsure))
    served.agent.script = [first, play(text="One to answer: **Lunch on Friday?**")]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")
    assert run["status"] == "needs_input" and run["summary"] == "It is waiting on your answer."
    asked = run["question"]
    assert asked["question"] == "Worth answering?" and asked["options"] == ["answer", "skip"]
    assert [b["label"] for b in asked["batch"]] == ["Lunch on Friday?"] and asked["decision"] == "worth"
    assert [s["title"] for s in run["steps"]] == ["Find Email", "Decided worth for 1 item"]  # reading never asked
    done = await answered(served, ana, run["id"], "1=answer")
    assert done["status"] == "done" and done["output"] == "One to answer: **Lunch on Friday?**"
    assert [s["title"] for s in done["steps"]] == ["Find Email", "Decided worth for 1 item", "Decided worth for 1 item"]
    again = served.agent.turns[1]
    assert again.session and "Lunch on Friday? (id m1): answer" in again.message
    verdicts = {d["item"]: (d["outcome"], d["by"]) for d in done["data"]["worth"]["decisions"]}
    assert verdicts == {"Lunch on Friday?": ("answer", "you"), "You won!": ("skip", "ada")}
    assert served.ada.outcomes(GATE)[-1] == "answer"  # the person's answer is a precedent now
    res = await served.http.get(f"/v1/bots/{bot['slug']}/decisions", headers=ana.headers)
    kept = {d["label"]: (d["now"], d["who"]) for d in res.json()["decisions"]}
    assert kept == {"Lunch on Friday?": ("answer", "you"), "You won!": ("skip", "ada")}
    assert (done["input_tokens"], done["output_tokens"]) == (2000, 400)  # both goes metered


async def test_an_action_waits_for_the_persons_yes_to_that_very_call(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    served.agent.script = [play((SEND, REPLY)), play((SEND, REPLY), text="Sent.")]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    asked = run["question"]
    assert run["status"] == "needs_input" and asked["approval"] and asked["question"] == "Send Email in Gmail?"
    assert "grace@navy.test" in asked["detail"] and asked["options"] == ["yes", "no"]
    assert served.pd.runs == []  # nothing was sent
    done = await answered(served, ana, run["id"], "yes")
    assert done["status"] == "done" and done["output"] == "Sent." and len(served.pd.runs) == 1
    assert [(s["title"], s["app"], s["ok"]) for s in done["steps"]] == [("Send Email", "Gmail", True)]
    assert "said yes" in served.agent.turns[1].message


async def test_a_yes_is_to_one_call_and_another_input_asks_again(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    other = {**REPLY, "to": ["everyone@navy.test"]}
    served.agent.script = [play((SEND, REPLY)), play((SEND, other))]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    again = await answered(served, ana, run["id"], "yes")
    assert again["status"] == "needs_input" and "everyone@navy.test" in again["question"]["detail"]
    assert served.pd.runs == []


async def test_a_no_carries_on_without_the_action(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    served.agent.script = [play((SEND, REPLY)), play(text="I did not send it.")]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    done = await answered(served, ana, run["id"], "no")
    assert done["status"] == "done" and served.pd.runs == [] and "said no" in served.agent.turns[1].message


async def test_a_turn_that_fails_fails_the_run_and_is_still_metered(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    served.agent.script = [fails("It took more steps than a run may: ask for less at once.")]
    run = await ran(served, ana, bot["slug"], "Do everything")
    assert run["status"] == "failed" and run["summary"].startswith("It failed: It took more steps")
    assert run["input_tokens"] == 10


async def test_a_bot_the_orchestrator_asked_asks_the_person_through_it_until_it_is_done(
    served: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "EVERY", 0.01)  # how often it looks at the run of the bot it asked
    ana = await person(engine, "Team")  # Free's five calls a second would refuse a go of this test
    gmail = await connected(served, ana, allow=False)
    await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    everyone = {**REPLY, "to": ["everyone@navy.test"]}
    served.agent.script = [
        play(("ask_bot", {"bot": "Inbox Cat", "task": "Reply to Grace"})),  # the orchestrator hands the task on
        play((SEND, REPLY)),  # Inbox Cat must ask before it sends
        play((SEND, everyone)),  # told yes, it tries another send: it asks again
        play((SEND, everyone), text="Sent to everyone."),
        play(text="Inbox Cat sent it to everyone."),  # the orchestrator, once Inbox Cat's run is over
    ]
    run = await ran(served, ana, "orchestrator", "Have Inbox Cat reply to Grace")
    assert run["status"] == "needs_input" and run["question"]["question"] == "Inbox Cat asks: Send Email in Gmail?"
    again = await answered(served, ana, run["id"], "yes")  # answered at the orchestrator's run: Inbox Cat's is
    assert again["status"] == "needs_input" and "everyone@navy.test" in again["question"]["detail"]
    assert served.pd.runs == [] and len(served.agent.turns) == 3  # the orchestrator waits again, with no go of its own
    theirs = (await served.http.get("/v1/bots/inbox-cat/runs", headers=ana.headers)).json()["runs"][0]
    assert theirs["status"] == "needs_input" and theirs["input"] == "Reply to Grace"
    sent = await answered(served, ana, theirs["id"], "yes")  # answered where Inbox Cat's own run waits
    assert (sent["status"], sent["output"]) == ("done", "Sent to everyone.") and len(served.pd.runs) == 1
    done = await run_of(served, ana, run["id"])  # and the orchestrator carried on by itself
    assert (done["status"], done["output"]) == ("done", "Inbox Cat sent it to everyone.")
    told = served.agent.turns[-1].message
    assert told.startswith("Inbox Cat finished. Its answer:\n\nSent to everyone.") and served.agent.turns[-1].session
