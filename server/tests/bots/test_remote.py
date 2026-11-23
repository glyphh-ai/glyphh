"""A bot's runs on the org's rrotor (docs/specs/bot-agent-loop.md, 6.2): sent there as one call of glyphh_bot's `agent`
(the bot's prompt, the message, its tools by name, its plugins, its limits, and where its tools are), dispatched
until its result comes back; the result kept once, from its own rrotor (the bot's words, or why it failed; only its
new tokens on the meter, at the org's own key's rate); and anything that keeps the call from going fails the run,
saying why. The tests play the rrotor (tests/bots/remote.py)."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid, NoBalance
from glyphh_server.llm import ledger
from glyphh_server.models import LlmBalance, LlmUsageDay
from glyphh_server.ops.bots import due, prices, remote
from glyphh_server.ops.bots.remote import runs_agents
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.protocol import Call
from tests.bots.conftest import DECIDE, FIND, SEND, Served, made_bot
from tests.bots.remote import OnRrotor, left, online, out, row, rrotor_fixture  # noqa: F401 (the fixture)
from tests.bots.test_schedules import _due, quiet  # noqa: F401 (quiet: no bot left due after a test)
from tests.db.helpers import Person, person

INPUTS: set[str] = {"system", "message", "tools", "plugins", "skills", "model", "effort", "limits", "resume"}


async def test_a_run_is_sent_to_its_rrotor_as_one_call_of_its_agent(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    _, rt, run = await out(on_rrotor, engine)
    assert run["status"] == "dispatched" and run["runs_on"] == str(rt.id) and run["kind"] == "bot"
    assert run["own_key"] is True and run["started_at"] and run["summary"] == ""
    to, sent = on_rrotor.hub.sent[-1]
    assert (
        to == rt.id and isinstance(sent, Call) and sent.run_id == uuid.UUID(run["id"]) and len(on_rrotor.hub.sent) == 1
    )
    assert (sent.program, sent.function, sent.version, sent.folders) == ("glyphh_bot", "agent", None, None)
    given = sent.inputs
    assert set(given) == INPUTS | {"tool_url", "tool_token", "claude"}  # no file tools: the bot has no folders
    assert given["message"] == "lunch" and given["resume"] is False and given["claude"] == "api"
    assert "You are Inbox Cat" in given["system"] and "Worth answering?" in given["system"]
    assert given["tool_url"] == f"https://api.glyphh.test/v1/bots/runs/{run['id']}/tool" and given["tool_token"]
    assert {t["name"]: t["read_only"] for t in given["tools"]} == {
        FIND: True,
        SEND: False,
        DECIDE: True,
        "ask_person": True,
    }
    send = next(t for t in given["tools"] if t["name"] == SEND)
    assert set(send) == {"name", "description", "input_schema", "read_only"}
    assert send["description"] == "Send an email from your Gmail account"
    assert send["input_schema"]["required"] == ["to", "subject"] and "gmail" not in send["input_schema"]["properties"]
    (notes,) = given["plugins"]
    assert (notes["name"], notes["code"]) == ("notes", []) and "skills/replies/SKILL.md" in notes["files"]
    assert given["skills"] == ["notes:replies"]
    assert (given["model"], given["effort"]) == ("claude-opus-5-5", "medium")
    assert given["limits"] == {"turns": 25, "seconds": 300, "tokens": 400_000}


async def test_a_run_with_nothing_said_is_sent_the_bots_standing_task(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    await out(on_rrotor, engine, said="", spec={"limits": {"turns": 7, "seconds": 60, "tokens": 9000}})
    given = on_rrotor.call().inputs
    assert given["message"] == "Answer the mail worth answering."
    assert given["limits"] == {"turns": 7, "seconds": 60, "tokens": 9000}
    assert [t["name"] for t in given["tools"]] == ["ask_person"]


async def test_its_result_is_kept_once_and_only_from_its_own_rrotor(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, run = await out(on_rrotor, engine)
    other = await online(engine, ada)
    await on_rrotor.landed(other, ada, run["id"], left(output="Not mine."))  # not from its rrotor: skipped
    assert (await on_rrotor.run(ada, run["id"]))["status"] == "dispatched"
    steps = [{"tool": FIND, "ok": True}]
    seq = await on_rrotor.landed(rt, ada, run["id"], left(output="Nothing new.", tokens=(1000, 200), steps=steps))
    ended = await on_rrotor.run(ada, run["id"])
    assert ended["status"] == "done" and ended["output"] == "Nothing new." and ended["summary"] == ""
    assert (ended["input_tokens"], ended["output_tokens"]) == (1000, 200) and ended["finished_at"]
    assert ended["question"] is None and ended["files"] == [] and ended["error"] == ""
    await on_rrotor.landed(rt, ada, run["id"], left("failed", reason="late"), seq=seq)  # a replay: skipped
    await on_rrotor.landed(rt, ada, run["id"], left("failed", reason="later"))  # it has ended: skipped
    assert (await on_rrotor.run(ada, run["id"]))["status"] == "done"
    await on_rrotor.landed(rt, ada, uuid.uuid4(), left())  # no run of it: not a bot's
    assert len(on_rrotor.hub.sent) == 1


async def test_a_run_that_fails_there_or_says_nothing_says_so(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, run = await out(on_rrotor, engine, plan="Enterprise")
    why = "The bot ran out of time: a run may take 300 seconds."
    await on_rrotor.landed(rt, ada, run["id"], left("failed", reason=why, tokens=(50, 5)))
    ended = await on_rrotor.run(ada, run["id"])
    assert (ended["status"], ended["error"], ended["input_tokens"]) == ("failed", why, 50) and ended["finished_at"]
    assert ended["summary"].startswith("It failed: The bot ran out of time")
    # a folder the machine's owner does not offer: the rrotor refuses the call in a plain sentence
    said = "/Users/ana/Documents is not in a folder this rrotor's owner shares with bots."
    refused = {"status": "failed", "step": "call", "prompt": None, "data": {"code": "E_FOLDER_REFUSED", "reason": said}}
    for result, error in (
        (refused, said),
        ({"status": "failed", "step": "agent", "data": None}, "The run failed on its rrotor."),
        ({"status": "cancelled", "step": "agent", "data": {}}, "The run failed on its rrotor."),
        ({"data": {"output": "Sent."}}, "The run failed on its rrotor."),  # no status: not a done
        (left(), "It finished without saying anything."),
        (left(output="Sent.", tokens="many"), ""),  # tokens that are not counts: none counted
        (left() | {"data": {"tokens": {"input_tokens": "many"}}}, "The rrotor's result could not be kept: invalid"),
    ):
        run = await on_rrotor.start(ada)
        await on_rrotor.landed(rt, ada, run["id"], result)
        ended = await on_rrotor.run(ada, run["id"])
        assert ended["error"].startswith(error), result
        done = result.get("status") == "done" and not error.startswith("The rrotor's result")
        assert ended["status"] == ("done" if done else "failed"), result


async def _past_its_allowance(engine: AsyncEngine, who: Person) -> None:
    """The org's plan's tokens this month used, with a balance: every token more is charged."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        await ledger.held(conn, who.org_id)
        used = {"period": ledger.period(), "tokens": 10**12, "micros": 10**9}
        await conn.execute(update(LlmBalance).where(LlmBalance.org_id == who.org_id).values(**used))


async def test_only_its_new_tokens_go_on_the_meter_at_the_own_keys_rate(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await out(on_rrotor, engine)
    await _past_its_allowance(engine, ada)
    change = {"action": "write", "path": "/Users/ana/Notes/a.md", "name": "Notes/a.md"}
    asks = left("needs_input", "Write Notes/a.md?", tokens=(1000, 200), approval=True, file=change)
    await on_rrotor.landed(rt, ada, run["id"], asks)
    own, glyphhs = (prices.charged("claude-opus-5-5", own_key=k) for k in (True, False))
    first = (await on_rrotor.run(ada, run["id"]))["cost_micros"]
    assert first == own.cost_micros(1000, 200, 1.0) and 0 < first < glyphhs.cost_micros(1000, 200, 1.0)
    await on_rrotor.answer(ada, run["id"], "no")
    # the rrotor says the run's tokens so far, through every go of it: only what is new is counted
    await on_rrotor.landed(rt, ada, run["id"], left(output="Left it.", tokens=(1500, 260)))
    ended = await on_rrotor.run(ada, run["id"])
    assert (ended["input_tokens"], ended["output_tokens"]) == (1500, 260)
    assert ended["cost_micros"] == first + own.cost_micros(500, 60, 1.0)
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        used = (await conn.execute(select(LlmUsageDay).where(LlmUsageDay.org_id == ada.org_id))).one()
    assert (used.input_tokens, used.output_tokens, used.requests) == (1500, 260, 2)
    assert used.charged_micros == ended["cost_micros"]
    # a result with no tokens of its own puts nothing on the meter
    run = await on_rrotor.start(ada)
    await on_rrotor.landed(rt, ada, run["id"], left(output="Hello!"))
    assert (await on_rrotor.run(ada, run["id"]))["cost_micros"] == 0


def test_which_rrotors_run_a_bot_as_an_agent() -> None:
    assert [runs_agents(v) for v in ("0.9.0", "0.9.1-rc1", "0.10.2", "1.0.0")] == [True] * 4
    assert [runs_agents(v) for v in ("0.8.9", "0.6.0", "", None, "latest")] == [False] * 5


@pytest.mark.parametrize("version", ["0.8.0", None])
async def test_a_rrotor_before_agents_fails_the_run_saying_to_update(
    on_rrotor: OnRrotor, engine: AsyncEngine, version: str | None
) -> None:
    ada = await person(engine)
    rt = await online(engine, ada, version=version)
    await made_bot(on_rrotor.s, ada, runs_on=str(rt.id))
    run = await on_rrotor.start(ada)
    assert run["status"] == "failed" and on_rrotor.hub.sent == []
    assert run["error"] == (
        f"Acme runs rrotor {version or 'an earlier version'}, which cannot run this bot: update it to rrotor 0.9.0 "
        "or later."
    )


async def test_a_call_that_cannot_go_fails_its_run_saying_why(
    on_rrotor: OnRrotor, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    on_rrotor.hub.up = False  # the rrotor's link dropped just now
    ada, _, run = await out(on_rrotor, engine)
    assert run["status"] == "failed" and "The bot's rrotor is not linked to Glyphh right now" in run["error"]
    on_rrotor.hub.up = True
    monkeypatch.setattr(calls, "LINK_MAX", 1000)
    run = await on_rrotor.start(ada)
    assert run["status"] == "failed" and "The bot's plugins and tools is" in run["error"]
    assert "more than a rrotor's link takes" in run["error"] and len(on_rrotor.hub.sent) == 1
    monkeypatch.undo()
    async with engine.begin() as conn:  # a rrotor that is not the org's
        await tenancy.enter(conn, ada.org_id)
        with pytest.raises(Invalid):
            await calls.linked(conn, uuid.uuid4())


async def test_a_run_is_refused_while_the_orgs_tokens_are_spent(
    on_rrotor: OnRrotor, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def spent(*_: Any) -> Any:
        raise NoBalance("Your plan's tokens this month are used.", reason="tokens")

    ada = await person(engine)
    rt = await online(engine, ada)
    await made_bot(on_rrotor.s, ada, runs_on=str(rt.id))
    monkeypatch.setattr(remote.meter, "admit", spent)
    res = await on_rrotor.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)
    assert res.status_code == 402 and res.json()["error"]["reason"] == "tokens" and on_rrotor.hub.sent == []
    listed = (await on_rrotor.s.http.get("/v1/bots/inbox-cat/runs", headers=ada.headers)).json()["runs"]
    assert listed == []  # refused before a run was made


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
    sent = on_rrotor.hub.last()
    assert isinstance(sent, Call) and on_rrotor.hub.sent[-1][0] == rt.id
    assert sent.inputs["message"] == "Answer the mail worth answering."  # its standing task
    assert (await row(engine, sent.run_id)).status == "dispatched"
