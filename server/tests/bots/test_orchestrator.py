"""The org's orchestrator (docs/specs/bot-agent-loop.md, 8): the one bot every org has from the start, listed first,
changed like any bot and never deleted; and what it does in a run: it sees the org's bots and hands a task to one,
which works under its own permission mode. A bot it asked that must ask the person stops the orchestrator's run with
the same question; answered at either run, the bot carries on and the orchestrator says what it said."""

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Bot, BotRun
from glyphh_server.ops import orgs
from glyphh_server.ops.bots import orchestrator
from glyphh_server.ops.bots.agent.turn import Ended, Turn
from tests.bots.agents import SESSION, fails, play
from tests.bots.conftest import SEND, Served, answered, connected, made_bot, ran, run_of
from tests.bots.fakes import MAIL
from tests.connector import granted, tool
from tests.db.helpers import Person, member, person

ORCH: str = "orchestrator"
REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
OTHER: dict[str, Any] = {**REPLY, "to": ["everyone@navy.test"]}
ASK: tuple[str, dict[str, Any]] = ("ask_bot", {"bot": "Inbox Cat", "task": "Reply to Grace"})
OWN: list[str] = ["ask_bot", "ask_person", "crew_start", "crew_status", "crew_stop", "list_bots"]


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "EVERY", 0.01)  # how often it looks at the run of the bot it asked


@pytest.fixture(name="ana")
async def ana_fixture(engine: AsyncEngine) -> Person:
    """Ana on Team: a faked go takes no time, and Free's five calls a second would refuse the sixth of a test."""
    return await person(engine, "Team")


async def bots_of(s: Served, who: Person) -> list[dict[str, Any]]:
    return list((await s.http.get("/v1/bots", headers=who.headers)).json()["bots"])


async def sender(s: Served, who: Person, **over: Any) -> dict[str, Any]:
    """Inbox Cat with Gmail's send tool, which its connection says nothing about: in its ask mode, sending asks."""
    gmail = await connected(s, who, allow=False)
    return await made_bot(s, who, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}], **over)


async def asked(s: Served, who: Person) -> tuple[dict[str, Any], str]:
    """The orchestrator's run stopped on the bot's question, and that bot's run."""
    run = await ran(s, who, ORCH, "Have Inbox Cat reply to Grace")
    assert run["status"] == "needs_input", run
    runs = (await s.http.get("/v1/bots/inbox-cat/runs", headers=who.headers)).json()["runs"]
    return run, runs[0]["id"]


async def until(s: Served, who: Person, run_id: str, status: str) -> dict[str, Any]:
    for _ in range(500):
        run = await run_of(s, who, run_id)
        if run["status"] == status:
            return run
        await asyncio.sleep(0.01)
    raise AssertionError(f"the run never was {status}: {run}")


async def test_every_org_has_one_orchestrator_from_the_start_listed_first(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    first = await bots_of(served, ana)
    assert [(b["slug"], b["name"], b["role"]) for b in first] == [(ORCH, "Orchestrator", ORCH)]
    mine = first[0]
    assert mine["instructions"].startswith("You are the orchestrator") and mine["model"] == "claude-opus-5-5"
    assert mine["task"] and len(mine["examples"]) == 3 and mine["spec"] == {"limits": {"seconds": 900}}
    await made_bot(served, ana, name="Aardvark", spec={})  # before it by name, after it in the list
    assert [(b["slug"], b["role"]) for b in await bots_of(served, ana)] == [(ORCH, ORCH), ("aardvark", "bot")]
    async with engine.begin() as conn:
        await orchestrator.ensure(conn, ana.org_id)  # safe to run again: it has one
        with pytest.raises(IntegrityError):  # and the database refuses a second
            async with conn.begin_nested():
                await conn.execute(insert(Bot).values(org_id=ana.org_id, slug="second", **orchestrator.DEFAULT))
        count = select(func.count()).select_from(Bot).where(Bot.org_id == ana.org_id, Bot.role == ORCH)
        assert (await conn.execute(count)).scalar_one() == 1
    grace = await member(engine, ana.org_id)  # a person moved into an org of their own gets theirs too
    async with engine.begin() as conn:
        own = await orgs.own_org(conn, grace.user_id, "Grace", grace.email)
        found = list(await conn.execute(select(Bot.slug, Bot.role).where(Bot.org_id == own)))
    assert own != ana.org_id and [tuple(r) for r in found] == [(ORCH, ORCH)]


async def test_an_org_with_bots_of_its_name_gets_it_under_the_next_free_slug(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    async def remade() -> str:
        async with engine.begin() as conn:
            await conn.execute(delete(Bot).where(Bot.org_id == ana.org_id, Bot.role == ORCH))
            await orchestrator.ensure(conn, ana.org_id)
            return str((await conn.scalars(select(Bot.slug).where(Bot.org_id == ana.org_id, Bot.role == ORCH))).one())

    async with engine.begin() as conn:  # an org from before there were orchestrators, its bots named as they liked
        await conn.execute(delete(Bot).where(Bot.org_id == ana.org_id))
    await made_bot(served, ana, name="Orchestrator", spec={})
    assert await remade() == "the-orchestrator"
    async with engine.begin() as conn:
        await conn.execute(delete(Bot).where(Bot.org_id == ana.org_id, Bot.role == ORCH))
    await made_bot(served, ana, name="The Orchestrator", spec={})
    assert await remade() == "glyphh-orchestrator"
    async with engine.begin() as conn:
        await conn.execute(delete(Bot).where(Bot.org_id == ana.org_id, Bot.role == ORCH))
    await made_bot(served, ana, name="Glyphh Orchestrator", spec={})
    last = await remade()
    assert last.startswith("orchestrator-") and len(last) == len("orchestrator-") + 6
    assert (await bots_of(served, ana))[0]["slug"] == last  # still first, whatever its slug


async def test_it_is_changed_like_any_bot_but_its_role_is_not_given_and_it_is_never_deleted(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    gmail = await connected(served, ana)
    change = {"name": "Maestro", "instructions": "You are Maestro. Hand work out.", "model": "claude-sonnet-5-5"}
    change |= {"effort": "high", "permission_mode": "auto", "task": "Say who is here.", "examples": ["Who is here?"]}
    change |= {"schedule": {"every": "day", "at": "09:00", "timezone": "America/Chicago"}}
    res = await served.http.patch(f"/v1/bots/{ORCH}", json=change, headers=ana.headers)
    assert res.status_code == 200, res.text
    got = res.json()
    assert {k: got[k] for k in change if k != "schedule"} == {k: v for k, v in change.items() if k != "schedule"}
    assert got["schedule"]["every"] == "day" and got["next_run_at"] and (got["slug"], got["role"]) == (ORCH, ORCH)
    scopes = {"connections": [{"connection_id": gmail["id"], "tools": ["gmail-find-email"]}]}
    res = await served.http.put(f"/v1/bots/{ORCH}/connections", json=scopes, headers=ana.headers)
    assert res.status_code == 200 and res.json()["connections"][0]["tools"] == ["gmail-find-email"]
    assert res.json()["role"] == ORCH
    res = await served.http.patch(f"/v1/bots/{ORCH}", json={"role": "bot"}, headers=ana.headers)
    assert res.status_code == 422  # its role is not a field of any request
    body = {"name": "Second", "instructions": "Be it.", "spec": {}, "role": ORCH}
    assert (await served.http.post("/v1/bots", json=body, headers=ana.headers)).status_code == 422
    res = await served.http.delete(f"/v1/bots/{ORCH}", headers=ana.headers)
    assert res.status_code == 409, res.text
    err = res.json()["error"]
    assert err["reason"] == ORCH and err["slug"] == ORCH
    assert err["message"] == "The orchestrator is always here: you can change it, but not delete it."
    _, auth = await granted(engine, ana)
    refused = await tool(served.http, auth, "bot_delete", slug=ORCH)
    assert refused["isError"] is True and refused["structuredContent"]["error"]["reason"] == ORCH
    assert "you can change it, but not delete it" in refused["content"][0]["text"]
    listed = (await tool(served.http, auth, "bots"))["content"][0]["text"]
    assert listed.startswith("Maestro (orchestrator, the orchestrator (never deleted)): ")
    await made_bot(served, ana, name="Poet", spec={})
    assert (await served.http.delete("/v1/bots/poet", headers=ana.headers)).status_code == 204  # any other bot goes
    assert [(b["name"], b["role"]) for b in await bots_of(served, ana)] == [("Maestro", ORCH)]


async def test_it_sees_the_bots_and_hands_a_task_to_one_and_hears_its_answer(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    await made_bot(served, ana, name="Poet", summary="Writes poems", spec={})
    lead = play(("list_bots", {}), ASK, ("ask_bot", {"bot": " inbox-cat ", "task": ""}), text="Inbox Cat found none.")
    served.agent.script = [lead, play(text="Nothing worth answering."), play(text="Still nothing.")]
    run = await ran(served, ana, ORCH, "Is there mail to answer?")
    assert run["status"] == "done" and run["output"] == "Inbox Cat found none."
    seen, heard, again = (h.value for h in lead.heard)  # type: ignore[attr-defined]
    assert seen == [
        {"bot": "Inbox Cat", "does": "Answers the mail worth answering"},
        {"bot": "Poet", "does": "Writes poems"},
    ]  # every bot but itself, by name
    assert heard == {"bot": "Inbox Cat", "status": "done", "answer": "Nothing worth answering."}
    assert again["answer"] == "Still nothing."  # a bot is found by its slug too
    assert [s["title"] for s in run["steps"]] == ["Looked at the bots", "Asked a bot", "Asked a bot"]
    mine, theirs, _ = served.agent.turns
    assert sorted(t.name for t in mine.tools) == OWN and all(t.read_only for t in mine.tools)
    assert theirs.message == "Reply to Grace" and not {t.name for t in theirs.tools} & {*OWN} - {"ask_person"}
    assert (
        await theirs.call("list_bots", {})
    ).value == "There is no tool list_bots: use only the tools you were given."
    assert served.agent.turns[2].message == "Answer the mail worth answering."  # no task given: its standing task
    runs = (await served.http.get("/v1/bots/inbox-cat/runs", headers=ana.headers)).json()["runs"]
    assert [r["input"] for r in runs] == ["", "Reply to Grace"] and all(r["status"] == "done" for r in runs)


async def test_a_bot_it_cannot_ask_is_said_plainly_and_it_goes_on(served: Served, ana: Person) -> None:
    await sender(served, ana)
    await made_bot(served, ana, name="Poet", spec={"limits": {"runs_per_day": 1}})
    await ran(served, ana, "poet", "A poem")  # its one run of the day
    served.agent.script = [play((SEND, REPLY))]
    waiting = await ran(served, ana, "inbox-cat", "Reply to Grace")  # it waits on the person: one live run a bot
    assert waiting["status"] == "needs_input"
    calls = [("ask_bot", {"bot": n, "task": "Go"}) for n in ("Nobody", "Orchestrator", "", "Inbox Cat", "Poet")]
    lead = play(*calls, ("ask_bot", {}), text="None of them could.")
    served.agent.script = [lead]
    run = await ran(served, ana, ORCH, "Ask everyone")
    assert run["status"] == "done" and [h.kind for h in lead.heard] == ["error"] * 6  # type: ignore[attr-defined]
    nobody, itself, unnamed, live, spent, nothing = (h.value for h in lead.heard)  # type: ignore[attr-defined]
    assert nobody == "There is no bot 'Nobody': list_bots says which there are."
    assert itself == "There is no bot 'Orchestrator': list_bots says which there are."  # it does not ask itself
    assert unnamed == "There is no bot '': list_bots says which there are." and "no bot None" in nothing
    assert live.startswith("Inbox Cat could not start: ") and "run" in live
    assert spent == "Poet could not do it: It has reached the most runs it may make in a day (1)."
    assert [s["ok"] for s in run["steps"]] == [False] * 6
    await answered(served, ana, waiting["id"], "no")
    again = play(ASK, text="It failed.")
    served.agent.script = [again, fails("Gmail is down.")]
    run = await ran(served, ana, ORCH, "Ask again")
    assert run["status"] == "done" and run["output"] == "It failed."
    assert again.heard[0].value == "Inbox Cat could not do it: Gmail is down."  # type: ignore[attr-defined]
    assert served.agent.turns[-1].message == "Reply to Grace"  # the bot's turn came after the orchestrator's began


async def test_the_bot_it_asked_asks_by_its_own_mode_and_the_answer_goes_to_that_bots_run(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    await sender(served, ana)
    res = await served.http.patch(f"/v1/bots/{ORCH}", json={"permission_mode": "auto"}, headers=ana.headers)
    assert res.json()["permission_mode"] == "auto"  # the orchestrator acts on its own: the bot it asks still asks
    served.agent.script = [play(ASK), play((SEND, REPLY))]
    run, child = await asked(served, ana)
    asks = run["question"]
    assert asks["question"] == "Inbox Cat asks: Send Email in Gmail?" and asks["approval"] is True
    assert asks["options"] == ["yes", "no"] and "grace@navy.test" in asks["detail"] and served.pd.runs == []
    async with engine.begin() as conn:
        kept = (await conn.execute(select(BotRun.question).where(BotRun.id == uuid.UUID(run["id"])))).scalar_one()
    assert (kept["child_run"], kept["child_bot"]) == (child, "Inbox Cat")
    theirs = await run_of(served, ana, child)
    assert theirs["status"] == "needs_input" and theirs["question"]["question"] == "Send Email in Gmail?"
    queue = (await served.http.get("/v1/bot-approvals", headers=ana.headers)).json()["runs"]
    assert {r["id"] for r in queue} == {run["id"], child}
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": "maybe"}, headers=ana.headers)
    assert res.status_code == 422  # the orchestrator's run takes the bot's question's answers
    served.agent.script = [play((SEND, REPLY), text="Sent to Grace."), play(text="Inbox Cat sent it.")]
    done = await answered(served, ana, run["id"], "yes")
    assert done["status"] == "done" and done["output"] == "Inbox Cat sent it." and len(served.pd.runs) == 1
    told = served.agent.turns[-1]
    assert told.message == "Inbox Cat finished. Its answer:\n\nSent to Grace.\n\nTell the person, plainly."
    assert told.session == SESSION  # the orchestrator's own session, carried on
    theirs = await run_of(served, ana, child)
    assert theirs["status"] == "done" and theirs["output"] == "Sent to Grace."


async def test_a_bot_that_acts_on_its_own_does_not_ask_whatever_the_orchestrators_mode(
    served: Served, ana: Person
) -> None:
    await sender(served, ana, permission_mode="auto")
    served.agent.script = [play(ASK, text="Done."), play((SEND, REPLY), text="Sent.")]
    run = await ran(served, ana, ORCH, "Have Inbox Cat reply to Grace")  # the orchestrator's own mode is ask
    assert run["status"] == "done" and len(served.pd.runs) == 1


async def test_answering_the_bots_own_run_carries_the_orchestrator_on(served: Served, ana: Person) -> None:
    await sender(served, ana)
    served.agent.script = [play(ASK), play((SEND, REPLY))]
    run, child = await asked(served, ana)
    served.agent.script = [play(text="I did not send it."), play(text="Inbox Cat did not send it.")]
    theirs = await answered(served, ana, child, "no")  # answered where the bot's own run waits
    assert theirs["status"] == "done" and theirs["output"] == "I did not send it."
    done = await run_of(served, ana, run["id"])
    assert done["status"] == "done" and done["output"] == "Inbox Cat did not send it." and served.pd.runs == []
    assert "Inbox Cat finished. Its answer:\n\nI did not send it." in served.agent.turns[-1].message
    assert (await served.http.get("/v1/bot-approvals", headers=ana.headers)).json()["runs"] == []


async def test_a_bot_that_asks_again_stops_the_orchestrator_again(served: Served, ana: Person) -> None:
    await sender(served, ana)
    served.agent.script = [play(ASK), play((SEND, REPLY))]
    run, child = await asked(served, ana)
    served.agent.script = [play((SEND, OTHER))]  # the yes was to that one call: another asks again
    again = await answered(served, ana, run["id"], "yes")
    assert again["status"] == "needs_input" and again["question"]["question"] == "Inbox Cat asks: Send Email in Gmail?"
    assert "everyone@navy.test" in again["question"]["detail"] and served.pd.runs == []
    assert len(served.agent.turns) == 3  # the orchestrator's agent was not woken to hear a question
    served.agent.script = [play(text="Not sent."), play(text="Inbox Cat sent nothing.")]
    done = await answered(served, ana, run["id"], "no")
    assert done["status"] == "done" and done["output"] == "Inbox Cat sent nothing."
    assert (await run_of(served, ana, child))["output"] == "Not sent."


async def test_what_ada_is_not_sure_of_is_asked_through_the_orchestrator_too(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    items = {"decision": "worth", "items": MAIL}
    served.agent.script = [play(("ask_bot", {"bot": "Inbox Cat", "task": "What is worth answering?"}))]
    served.agent.script += [play(("ask_person", {"question": "", **items}))]
    run, child = await asked(served, ana)
    asks = run["question"]
    assert asks["question"] == "Inbox Cat asks: Worth answering?" and asks["decision"] == "worth"
    assert [b["label"] for b in asks["batch"]] == ["Lunch on Friday?", "You won!"]
    served.agent.script = [play(text="One to answer."), play(text="Inbox Cat says one.")]
    done = await answered(served, ana, run["id"], "1=answer rest=skip")
    assert done["status"] == "done" and done["output"] == "Inbox Cat says one."
    theirs = await run_of(served, ana, child)
    assert {d["item"]: d["outcome"] for d in theirs["data"]["worth"]["decisions"]} == {
        "Lunch on Friday?": "answer",
        "You won!": "skip",
    }
    assert served.ada.outcomes("bot-inbox-cat-gate-worth") == ["answer", "skip"]  # learned by the bot's own decision


async def test_a_bots_run_ended_another_way_is_told_when_the_orchestrator_is_answered(
    served: Served, ana: Person
) -> None:
    await sender(served, ana)
    served.agent.script = [play(ASK), play((SEND, REPLY))]
    run, child = await asked(served, ana)
    res = await served.http.post(f"/v1/bot-runs/{child}/cancel", headers=ana.headers)
    assert res.status_code == 200 and res.json()["status"] == "failed"
    served.agent.script = [play(text="Inbox Cat's run was cancelled.")]
    done = await answered(served, ana, run["id"], "yes")  # the bot's run no longer takes an answer
    assert done["status"] == "done" and done["output"] == "Inbox Cat's run was cancelled."
    assert served.agent.turns[-1].message == "Inbox Cat could not do it: cancelled. Tell the person."
    assert served.pd.runs == []


async def test_a_bot_still_working_when_the_wait_runs_out_is_said_so(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "WAIT_SECONDS", 0.03)
    await sender(served, ana)
    free = asyncio.Event()

    async def slow(turn: Turn) -> Ended:
        await free.wait()
        return await play((SEND, REPLY), text="Sent at last.")(turn)

    lead = play(ASK, text="Inbox Cat is still at it.")
    served.agent.script = [lead, slow]
    res = await served.http.post(f"/v1/bots/{ORCH}/runs", json={"input": "Reply"}, headers=ana.headers)
    done = await until(served, ana, res.json()["id"], "done")
    assert done["output"] == "Inbox Cat is still at it."
    assert lead.heard[0].value == {"bot": "Inbox Cat", "status": "still working", "answer": ""}  # type: ignore[attr-defined]
    free.set()
    await served.settled()  # the bot's run stops to ask, with no orchestrator's run waiting on it
    child = (await served.http.get("/v1/bots/inbox-cat/runs", headers=ana.headers)).json()["runs"][0]
    assert child["status"] == "needs_input"
    await served.http.post(f"/v1/bot-runs/{child['id']}/cancel", headers=ana.headers)
    free.clear()
    served.agent.script = [play(ASK), play((SEND, REPLY))]
    monkeypatch.setattr(orchestrator, "WAIT_SECONDS", 600.0)  # the bot gets to its question however slow the machine
    run, child_id = await asked(served, ana)
    monkeypatch.setattr(orchestrator, "WAIT_SECONDS", 0.03)
    served.agent.script = [slow, play(text="It is taking longer.")]
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": "yes"}, headers=ana.headers)
    assert res.status_code == 202
    done = await until(served, ana, run["id"], "done")
    assert done["output"] == "It is taking longer."
    assert served.agent.turns[-1].message == "Inbox Cat is still working on it. Tell the person it is taking longer."
    free.set()
    await served.settled()
    assert (await run_of(served, ana, child_id))["output"] == "Sent at last."
