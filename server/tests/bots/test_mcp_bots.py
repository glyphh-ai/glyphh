"""The connector's bots, runs and connections tools, called as Claude calls them: a bot made as an agent, scoped, said
something to (its agent faked: tests/bots/agents.py), its questions answered, a run cancelled, a decision corrected."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.agents import play
from tests.bots.conftest import BOTS, FIND, SEND, TOOLS, Served, asks, inbox, serve
from tests.bots.fakes import MAIL, FakePipedream, account
from tests.connector import granted, rpc, tool
from tests.db.helpers import person

SKILLS = {"replies": "---\nname: replies\ndescription: How\n---\n\nOne paragraph.\n"}
REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}


def text(got: dict[str, Any]) -> str:
    return str(got["content"][0]["text"])


async def test_a_bot_is_made_scoped_run_answered_and_corrected_through_the_connector(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    guide = text(await tool(served.http, auth, "bot_guide"))
    assert "a Claude agent a person talks to" in guide and "standing task" in guide and '"loop"' not in guide
    only = text(await tool(served.http, auth, "bots"))  # the org's orchestrator is there from the start
    assert only.startswith("Orchestrator (orchestrator, the orchestrator (never deleted)): Answers you and hands")
    assert text(await tool(served.http, auth, "bots", q="inbox")) == "The org has no bots yet."
    link = await tool(served.http, auth, "connection_link", app="gmail")
    assert link["isError"] is False and "ctok_1" in link["structuredContent"]["url"]
    served.pd.accounts.append(account("apn_9"))
    found = (await tool(served.http, auth, "connections"))["structuredContent"]["connections"]
    offered = await tool(served.http, auth, "connection_tools", connection_id=found[0]["id"])
    assert [t["key"] for t in offered["structuredContent"]["tools"]] == ["gmail-send-email", "gmail-find-email"]
    assert "gmail-find-email: Find Email (ask)" in text(offered)  # never set: it asks
    apps = await tool(served.http, auth, "connection_apps", q="sla")
    assert apps["structuredContent"]["apps"][0]["slug"] == "slack"
    scopes = [{"connection_id": found[0]["id"], "tools": TOOLS}]
    given = {"name": "Inbox Cat", "instructions": "Be kind.", "spec": inbox(), "skills": SKILLS, "connections": scopes,
             "task": "Answer the mail worth answering.", "examples": ["Anything worth answering?"]}  # fmt: skip
    made = (await rpc(served.http, auth, "tools/call", name="bot_create", arguments=given))["result"]
    assert made["isError"] is False, made
    assert text(made) == (
        "Made Inbox Cat (inbox-cat): no summary; decides worth; claude-opus-5-5 at medium effort; schedule Off; "
        "runs on Glyphh cloud. bot_run runs it."
    )
    assert made["structuredContent"]["task"] == "Answer the mail worth answering."
    listed = text(await tool(served.http, auth, "bots")).splitlines()
    assert listed[0].startswith("Orchestrator (") and listed[1].startswith("Inbox Cat (inbox-cat)")
    assert (await tool(served.http, auth, "bot", slug="inbox-cat"))["structuredContent"]["slug"] == "inbox-cat"
    scoped = await tool(served.http, auth, "bot_connections_set", slug="inbox-cat", connections=scopes)
    assert scoped["structuredContent"]["connections"][0]["tools"] == TOOLS

    served.agent.script = [play((FIND, {"q": "is:unread"}), asks(MAIL)), play((SEND, REPLY))]
    started = await tool(served.http, auth, "bot_run", slug="inbox-cat", input="What is worth answering?")
    assert started["isError"] is False and started["structuredContent"]["status"] == "queued"
    assert "bot_run_get follows it" in text(started)
    run_id = started["structuredContent"]["id"]
    await served.settled()
    queue = await tool(served.http, auth, "bot_approvals")
    assert "It asks: Worth answering? (answer, skip); answer like 1=answer 2=skip" in text(queue)
    assert [r["id"] for r in queue["structuredContent"]["runs"]] == [run_id]
    assert [r["id"] for r in served.pd.runs] == ["gmail-find-email"]  # reading never asked
    carried = await tool(served.http, auth, "bot_run_answer", run_id=run_id, answer={"1": "answer", "2": "skip"})
    assert "carries on" in text(carried)
    await served.settled()
    asked = text(await tool(served.http, auth, "bot_run_get", run_id=run_id))
    assert "needs_input" in asked and "It asks: Send Email in Gmail? (yes, no)" in asked and "answer like" not in asked
    cancelled = await tool(served.http, auth, "bot_run_cancel", run_id=run_id)
    assert "cancelled" in text(cancelled) and cancelled["structuredContent"]["status"] == "failed"
    assert text(await tool(served.http, auth, "bot_approvals")) == "No bot is waiting on you."
    modes = {"gmail-find-email": "allow", "gmail-send-email": "deny"}
    set_ = await tool(served.http, auth, "connection_permissions_set", connection_id=found[0]["id"], permissions=modes)
    assert text(set_) == "Gmail ada@gmail.test: gmail-find-email allow, gmail-send-email deny."
    assert set_["structuredContent"]["permissions"] == modes
    served.agent.script = [play((SEND, REPLY), text="Gmail would not let me send it.")]
    again = (await tool(served.http, auth, "bot_run", slug="inbox-cat", input="Reply"))["structuredContent"]["id"]
    await served.settled()
    blocked = await tool(served.http, auth, "bot_run_get", run_id=again)
    assert blocked["structuredContent"]["status"] == "done" and "Gmail would not let me send it." in text(blocked)
    assert [(s["title"], s["ok"]) for s in blocked["structuredContent"]["steps"]] == [("Send Email", False)]
    assert [r["id"] for r in served.pd.runs] == ["gmail-find-email"]  # found once, never sent
    listed = await tool(served.http, auth, "bot_runs", slug="inbox-cat")
    assert "$0.0" in text(listed) and len(listed["structuredContent"]["runs"]) == 2
    assert "failed, 2400 tokens" in text(listed) and "cancelled" in text(listed)
    fixed = await tool(served.http, auth, "bot_run_wrong", run_id=run_id, outcome="skip", item="m1")
    assert text(fixed) == "Decision worth said answer; Ada learned skip."
    gates = await tool(served.http, auth, "bot_gates", slug="inbox-cat")
    assert text(gates) == "worth: 3 precedents"  # the person's two answers and the correction

    changed = await tool(served.http, auth, "bot_update", slug="inbox-cat", summary="Keeps the inbox", task="Go.")
    assert (changed["structuredContent"]["summary"], changed["structuredContent"]["task"]) == ("Keeps the inbox", "Go.")
    assert text(changed).startswith("Changed Inbox Cat (inbox-cat): Keeps the inbox; decides worth;")
    assert ", last run done; schedule Off" in text(changed)
    priced = text(await tool(served.http, auth, "bot_models"))
    assert "claude-opus-5-5: $4.8/$24 per Mtok on Glyphh's key, $0.8/$4 on the org's own" in priced
    assert (await tool(served.http, auth, "bot_delete", slug="inbox-cat"))["isError"] is False
    missing = await tool(served.http, auth, "bot", slug="inbox-cat")
    assert missing["isError"] is True and missing["structuredContent"]["error"]["code"] == "E_NOT_FOUND"


async def test_the_tools_say_a_bot_is_an_agent_not_a_loop(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    listed = {t["name"]: t for t in (await rpc(served.http, auth, "tools/list"))["result"]["tools"]}
    for name in ("bots", "bot", "bot_create", "bot_update", "bot_run", "bot_run_get", "bot_approvals"):
        said = listed[name]["description"]
        assert "loop" not in said and "$input" not in said and " step" not in said, (name, said)
    assert "its task (what it does when it runs on its own)" in listed["bot_create"]["description"]
    assert "The orchestrator is never deleted" in listed["bot_delete"]["description"]
    assert {"task", "examples"} <= set(listed["bot_create"]["inputSchema"]["properties"])
    assert "role" not in listed["bot_update"]["inputSchema"]["properties"]
    refused = await tool(served.http, auth, "bot_update", slug="orchestrator", role="bot")
    assert refused["isError"] is True  # a role is not something a bot is given


async def test_a_bot_with_no_gates_on_the_orgs_own_key_and_connections_off(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    await served.http.put("/v1/bot-key", json={"key": "sk-ant-api03-the-orgs-own-key"}, headers=ada.headers)
    plain = {"name": "Poet", "instructions": "Write.", "spec": {}}
    made = (await rpc(served.http, auth, "tools/call", name="bot_create", arguments=plain))["result"]
    assert made["isError"] is False and "decides nothing" in text(made), made
    assert text(await tool(served.http, auth, "bot_runs", slug="poet")) == "No runs yet."
    served.agent.script = [play(text="Roses are red.")]
    run_id = (await tool(served.http, auth, "bot_run", slug="poet", input="cats"))["structuredContent"]["id"]
    await served.settled()
    said = text(await tool(served.http, auth, "bot_run_get", run_id=run_id))
    assert "done, 1200 tokens, on the org's own key. Roses are red." in said
    assert served.agent.turns[0].message == "cats" and [t.name for t in served.agent.turns[0].tools] == ["ask_person"]
    assert text(await tool(served.http, auth, "bot_gates", slug="poet")) == "The bot has no decisions."
    assert "last run done" in text(await tool(served.http, auth, "bots", q="poet"))
    assert "af_heart (American female)" in text(await tool(served.http, auth, "bot_voices"))
    places = text(await tool(served.http, auth, "bot_places"))
    assert places == "Glyphh cloud (cloud): none\n(bot_create and bot_update take the id as runs_on)"
    async for s in serve(BOTS.model_copy(update={"pipedream_project_id": ""}), FakePipedream()):
        off = await tool(s.http, auth, "connections")
        assert off["isError"] is True and off["structuredContent"]["error"]["reason"] == "pipedream_off"
