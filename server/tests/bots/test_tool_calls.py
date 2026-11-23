"""A bot on a rrotor calls its tools on the server (POST /v1/bots/runs/{id}/tool, bearer its run's tool token;
docs/specs/bot-agent-loop.md, 6.2): every call lands at the desk a cloud run uses, so a connection's tool runs as the
org, one its connection denies is refused, one to ask about stops the run with its question (`{ask: true}`) and runs
only on the person's yes to that very call, once; `decide` is Ada's; `fetch` reads only the bot's hosts; a plugin's
script runs only when declared. Any other token, or a run not out on its rrotor, opens nothing."""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotPlugin
from glyphh_server.ops.bots import cloud, remote_in, tool_calls
from glyphh_server.ops.link.protocol import Call, Continue
from tests.bots.conftest import DECIDE, FIND, SEND, connected, inbox, made_bot
from tests.bots.fakes import MAIL
from tests.bots.remote import OnRrotor, left, logged, online, out, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import Person, person
from tests.link import Rt

REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
ITEMS: dict[str, Any] = {"decision": "worth", "items": MAIL}
FOUND: dict[str, Any] = {"result": {"exports": {"$summary": "Found"}, "ret": MAIL}}  # what Gmail's search answered
GATE: str = "bot-inbox-cat-gate-worth"
SCRIPT: str = "skills/tidy/scripts/tidy.py"
TIDY: dict[str, str] = {
    ".claude-plugin/plugin.json": json.dumps({"name": "tidy", "version": "1.2.0"}),
    "skills/tidy/SKILL.md": "---\nname: tidy\ndescription: Tidy\n---\n\nRun the script.\n",
    SCRIPT: "print('tidied')\n",
    "glyphh.json": json.dumps({"code": [{"skill": "tidy", "scripts": [SCRIPT], "why": "It renames files."}]}),
}


async def _asking(r: OnRrotor, engine: AsyncEngine, **more: Any) -> tuple[Person, Rt, dict[str, Any]]:
    """A run out on its rrotor of an inbox bot whose Gmail connection sets neither tool (or as `modes` set them)."""
    ada = await person(engine)
    rt = await online(engine, ada)
    gmail = await connected(r.s, ada, allow=False)
    if modes := more.pop("modes", None):
        url = f"/v1/connections/{gmail['id']}/permissions"
        assert (await r.s.http.put(url, json={"permissions": modes}, headers=ada.headers)).status_code == 200
    scopes = [{"connection_id": gmail["id"], "tools": ["gmail-find-email", "gmail-send-email"]}]
    await made_bot(r.s, ada, runs_on=str(rt.id), connections=scopes, **more)
    return ada, rt, await r.start(ada)


async def _waits(r: OnRrotor, rt: Rt, who: Person, run_id: str, asked: Any) -> dict[str, Any]:
    """The rrotor ends its turn on the server's `{ask: true}`: the run as it then waits."""
    assert asked["ask"] is True
    await r.landed(rt, who, run_id, left("needs_input", asked["question"], options=None))
    return await r.run(who, run_id)


async def test_only_the_runs_own_token_opens_its_tools_while_it_is_out(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await out(on_rrotor, engine)
    token, secret = on_rrotor.call().inputs["tool_token"], on_rrotor.s.app.state.bots.settings.secret_key
    mine = {"run": run["id"], "org": str(ada.org_id)}
    other = await on_rrotor.start(await _other(on_rrotor, engine))
    for bad in (
        None,
        "not-a-token",
        token[:-2] + "00",
        on_rrotor.call().inputs["tool_token"],  # another run's
        remote_in.signed.sign(secret, {"k": "other", **mine}, 60),
        remote_in.signed.sign(secret, {"k": remote_in.KIND, **mine}, -1),  # expired
        remote_in.signed.sign("another-secret", {"k": remote_in.KIND, **mine}, 60),
    ):
        status, said = await on_rrotor.post(run["id"], bad, FIND, {"q": "x"})
        assert status == 401 and said["error"]["message"] == remote_in.BAD_TOKEN, bad
    assert (await on_rrotor.post(other["id"], token, FIND))[0] == 401
    assert (await on_rrotor.post(run["id"], token, "", {}))[0] == 422  # a tool is named
    assert on_rrotor.s.pd.runs == []
    assert (await on_rrotor.post(run["id"], token, FIND, {"q": "x"}))[1] == FOUND
    # the token opens the run only while it is out on its rrotor: not while it waits, nor once it ended
    change = {"action": "write", "path": "/Users/ana/Notes/a.md", "name": "Notes/a.md"}
    await on_rrotor.landed(rt, ada, run["id"], left("needs_input", "Write Notes/a.md?", approval=True, file=change))
    with logged() as said:
        assert (await on_rrotor.post(run["id"], token, FIND, {"q": "x"}))[1] == {"error": tool_calls.NOT_OUT}
    assert [(r.getMessage(), r.tool, r.why) for r in said] == [("bot tool call refused", FIND, tool_calls.NOT_OUT)]
    await on_rrotor.answer(ada, run["id"], "no")
    await on_rrotor.landed(rt, ada, run["id"], left(output="Left it."))
    for name in (FIND, "file_change", "run_script"):
        assert (await on_rrotor.post(run["id"], token, name, {}))[1] == {"error": tool_calls.NOT_OUT}
    assert len(on_rrotor.s.pd.runs) == 1


async def _other(r: OnRrotor, engine: AsyncEngine) -> Person:
    who = await person(engine)
    rt = await online(engine, who)
    await made_bot(r.s, who, runs_on=str(rt.id))
    return who


async def test_a_connections_tool_runs_as_the_org_and_the_run_notes_it(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, _, run = await out(on_rrotor, engine)
    assert await on_rrotor.tool(run["id"], FIND, {"q": "lunch"}) == FOUND
    ran = on_rrotor.s.pd.runs[-1]
    assert ran["id"] == "gmail-find-email" and ran["external_user_id"] == f"org_{ada.org_id}"
    assert ran["configured_props"]["q"] == "lunch" and ran["configured_props"]["gmail"] == {"authProvisionId": "apn_1"}
    assert await on_rrotor.tool(run["id"], FIND, "junk") == FOUND  # an input that is no object: none
    assert await on_rrotor.tool(run["id"], "slack_send", {}) == {
        "error": "There is no tool slack_send: use only the tools you were given."
    }
    on_rrotor.s.pd.fail_run = True
    failed = await on_rrotor.tool(run["id"], FIND, {"q": "lunch"})
    assert set(failed) == {"error"} and "revoked" in failed["error"]
    steps = (await on_rrotor.run(ada, run["id"]))["steps"]
    assert [(s["title"], s["app"], s["ok"]) for s in steps] == [("Find Email", "Gmail", True)] * 2 + [
        ("Find Email", "Gmail", False)
    ]


async def test_a_tool_its_connection_denies_is_refused_and_logged(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    modes = {"gmail-send-email": "deny", "gmail-find-email": "ask"}
    ada, _, run = await _asking(on_rrotor, engine, modes=modes, permission_mode="auto")
    with logged() as said:
        refused = await on_rrotor.tool(run["id"], SEND, REPLY)
    assert refused == {
        "error": "Send Email is blocked on the Gmail connection. Tell the person; they can allow it on that connection."
    }
    assert on_rrotor.s.pd.runs == []
    assert [r.getMessage() for r in said] == ["bot tool refused", "bot tool call refused"]
    assert (said[1].run_id, said[1].tool, said[1].why) == (run["id"], SEND, refused["error"])
    # and one its connection allows runs; Act on its own asks about nothing
    assert "result" in await on_rrotor.tool(run["id"], FIND, {"q": "x"})
    steps = (await on_rrotor.run(ada, run["id"]))["steps"]
    assert [(s["title"], s["ok"]) for s in steps] == [("Send Email", False), ("Find Email", True)]


async def test_a_tool_to_ask_about_stops_the_run_and_runs_on_the_persons_yes_to_that_call_once(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _asking(on_rrotor, engine)
    assert "result" in await on_rrotor.tool(run["id"], FIND, {"q": "is:unread"})  # reading never asks
    asked = await on_rrotor.tool(run["id"], SEND, REPLY)
    assert asked == {"ask": True, "question": "Send Email in Gmail?"}
    assert (await on_rrotor.run(ada, run["id"]))["status"] == "dispatched"  # until the rrotor ends its turn
    waiting = await _waits(on_rrotor, rt, ada, run["id"], asked)
    question = waiting["question"]
    assert waiting["status"] == "needs_input" and question["question"] == "Send Email in Gmail?"
    assert question["approval"] is True and question["options"] == ["yes", "no"]
    assert question["tool"] == "gmail-send-email" and "grace@navy.test" in question["detail"]
    queue = (await on_rrotor.s.http.get("/v1/bot-approvals", headers=ada.headers)).json()["runs"]
    assert [(q["id"], q["kind"], q["runs_on"]) for q in queue] == [(run["id"], "bot", str(rt.id))]
    assert len(on_rrotor.s.pd.runs) == 1  # nothing was sent
    assert (await on_rrotor.answer(ada, run["id"], "yes"))["status"] == "dispatched"
    carried = on_rrotor.hub.last()
    assert isinstance(carried, Continue) and carried.answer.startswith("The person said yes to that.")
    # the yes is to that very call: another input asks again, and is not sent
    everyone = {**REPLY, "to": ["everyone@navy.test"]}
    assert (await on_rrotor.tool(run["id"], SEND, everyone))["ask"] is True
    assert "result" in await on_rrotor.tool(run["id"], SEND, REPLY)
    assert [p["id"] for p in on_rrotor.s.pd.runs] == ["gmail-find-email", "gmail-send-email"]
    again = await on_rrotor.tool(run["id"], SEND, REPLY)  # used up
    assert again["ask"] is True and len(on_rrotor.s.pd.runs) == 2
    # a no keeps nothing
    await _waits(on_rrotor, rt, ada, run["id"], again)
    await on_rrotor.answer(ada, run["id"], "no")
    assert on_rrotor.hub.last().answer.startswith("The person said no to that.")
    assert (await on_rrotor.tool(run["id"], SEND, REPLY))["ask"] is True and len(on_rrotor.s.pd.runs) == 2


def _sure_of_spam(r: OnRrotor) -> None:
    """Ada knows `You won!` is to skip, and is not sure of anything else."""
    r.s.ada.cases[GATE].append(({}, "skip"))
    r.s.ada.rule[GATE] = lambda case: ("skip", 0.95) if "won" in case["m"]["s"]["subject"] else ("answer", 0.4)


async def test_decide_is_adas_and_what_the_person_answers_is_learned(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, run = await out(on_rrotor, engine)
    _sure_of_spam(on_rrotor)
    spam = {"decision": "worth", "items": MAIL[1:]}
    sure = await on_rrotor.tool(run["id"], DECIDE, spam)
    assert [(d["outcome"], d["by"], d["sure"]) for d in sure["result"]] == [("skip", "ada", True)]  # it stands
    for bad in ({"decision": "nope", "items": MAIL}, {"decision": "worth", "items": []}, {"items": ["x"]}, None):
        assert (await on_rrotor.tool(run["id"], DECIDE, bad))["error"].startswith("Give a decision's name")
    unsure = (await on_rrotor.tool(run["id"], DECIDE, {"decision": "worth", "items": MAIL[:1]}))["result"]
    assert [(d["outcome"], d["sure"]) for d in unsure] == [("answer", False)]  # Ada's guess, not sure of it
    asked = await on_rrotor.tool(run["id"], "ask_person", {"question": "", "decision": "worth", "items": MAIL[:1]})
    assert asked == {"ask": True, "question": "Worth answering?"}
    waiting = await _waits(on_rrotor, rt, ada, run["id"], asked)
    question = waiting["question"]
    assert question["options"] == ["answer", "skip"] and question["decision"] == "worth"
    assert [b["label"] for b in question["batch"]] == ["Lunch on Friday?"]
    await on_rrotor.answer(ada, run["id"], "1=answer")
    carried = on_rrotor.hub.last()
    assert isinstance(carried, Continue) and "Lunch on Friday? (id m1): answer" in carried.answer
    assert on_rrotor.s.ada.outcomes(GATE)[-1] == "answer"  # the person's answer is a precedent now
    await on_rrotor.landed(rt, ada, run["id"], left(output="One to answer."))
    done = await on_rrotor.run(ada, run["id"])
    assert done["status"] == "done" and [s["title"] for s in done["steps"]] == [
        "Decided worth for 1 item",
        "Decided worth for 1 item",
    ]
    assert {d["item"]: (d["outcome"], d["by"]) for d in done["data"]["worth"]["decisions"]} == {
        "You won!": ("skip", "ada"),
        "Lunch on Friday?": ("answer", "you"),
    }
    kept = (await on_rrotor.s.http.get("/v1/bots/inbox-cat/decisions", headers=ada.headers)).json()["decisions"]
    assert ("Lunch on Friday?", "answer", "you") in {(d["label"], d["now"], d["who"]) for d in kept}


async def test_fetch_gets_json_only_from_the_bots_hosts(
    on_rrotor: OnRrotor, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetched: list[Any] = []

    def fake(req: Any, timeout: float) -> Any:
        fetched.append((req.full_url, req.headers))
        return {"weather": "sun"}

    monkeypatch.setattr(cloud, "fetch", fake)
    _, _, run = await out(on_rrotor, engine, spec={"hosts": ["api.example.com"]})
    tool, _ = on_rrotor.call().inputs["tools"]  # and ask_person
    assert (tool["name"], tool["read_only"]) == ("fetch", True) and "api.example.com" in tool["description"]
    given = {"url": "https://api.example.com/y", "headers": {"X-Key": "k"}}
    assert await on_rrotor.tool(run["id"], "fetch", given) == {"result": {"weather": "sun"}}
    assert fetched[-1][0] == "https://api.example.com/y" and fetched[-1][1]["X-key"] == "k"
    for bad in ("http://api.example.com/x", "https://other.example.com/x"):
        said = await on_rrotor.tool(run["id"], "fetch", {"url": bad})
        assert "is not https on one of the bot's hosts (api.example.com)" in said["error"]
    assert (await on_rrotor.tool(run["id"], "fetch", {"url": 3}))["error"].startswith("fetch takes a URL")
    assert len(fetched) == 1
    # a bot that names no hosts has no fetch at all
    run = await on_rrotor.start(await _other(on_rrotor, engine))
    assert (await on_rrotor.tool(run["id"], "fetch", given))["error"].startswith("There is no tool fetch")


async def _with_script(r: OnRrotor, engine: AsyncEngine, **over: Any) -> tuple[Person, Rt, dict[str, Any]]:
    """A run out on its rrotor of a bot with a plugin that declares one script."""
    ada = await person(engine)
    rt = await online(engine, ada)
    bot = await made_bot(r.s, ada, runs_on=str(rt.id), spec=inbox(), connections=[], **over)
    plugin = {"org_id": ada.org_id, "bot_id": bot["id"], "name": "tidy", "version": "1.2.0", "files": TIDY}
    async with engine.begin() as conn:
        await conn.execute(insert(BotPlugin).values(**plugin, source="template:tidy"))
    return ada, rt, await r.start(ada)


async def test_a_plugins_script_runs_only_when_declared_and_asks_under_ask_me_first(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _with_script(on_rrotor, engine)
    sent = on_rrotor.call()
    assert isinstance(sent, Call) and sent.inputs["skills"] == ["tidy:tidy", "notes:replies"]
    tidy = next(p for p in sent.inputs["plugins"] if p["name"] == "tidy")
    assert tidy["code"] == [{"skill": "tidy", "scripts": [SCRIPT]}] and tidy["files"][SCRIPT] == "print('tidied')\n"
    assert "run_script" not in {t["name"] for t in sent.inputs["tools"]}  # the machine's own tool, not the server's
    told = {"plugin": "tidy", "script": SCRIPT, "args": ["--dry"]}
    for bad in ({**told, "script": "skills/tidy/scripts/other.py"}, {**told, "plugin": "notes"}, {}, None):
        assert await on_rrotor.tool(run["id"], "run_script", bad) == {"error": tool_calls.NO_SCRIPT}
    asked = await on_rrotor.tool(run["id"], "run_script", told)
    assert asked == {"ask": True, "question": "Run tidy.py?"}
    waiting = await _waits(on_rrotor, rt, ada, run["id"], asked)
    assert waiting["question"]["tool"] == "run_script" and "--dry" in waiting["question"]["detail"]
    await on_rrotor.answer(ada, run["id"], "yes")
    assert (await on_rrotor.tool(run["id"], "run_script", {**told, "args": ["--for-real"]}))["ask"] is True
    assert await on_rrotor.tool(run["id"], "run_script", told) == {"result": {"allowed": True}}
    assert (await on_rrotor.tool(run["id"], "run_script", told))["ask"] is True  # the yes was to one run of it
    steps = (await on_rrotor.run(ada, run["id"]))["steps"]
    assert [(s["tool"], s["title"], s["ok"]) for s in steps] == [("run_script", "Run tidy.py", True)]


async def test_a_bot_that_acts_on_its_own_runs_its_scripts_at_once(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    _, _, run = await _with_script(on_rrotor, engine, permission_mode="auto")
    told = {"plugin": "tidy", "script": SCRIPT}
    assert await on_rrotor.tool(run["id"], "run_script", told) == {"result": {"allowed": True}}
    assert uuid.UUID(run["id"]) == on_rrotor.call().run_id
