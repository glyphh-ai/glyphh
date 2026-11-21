"""The connector's bots, runs and connections tools, called as Claude calls them."""

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.conftest import BOTS, TOOLS, Served, inbox, serve
from tests.bots.fakes import FakePipedream, account
from tests.connector import granted, rpc, tool
from tests.db.helpers import person

SKILLS = {"replies": "---\nname: replies\ndescription: How\n---\n\nOne paragraph.\n"}


async def test_a_bot_is_made_scoped_run_answered_and_corrected_through_the_connector(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    assert "gate" in (await tool(served.http, auth, "bot_guide"))["content"][0]["text"]
    assert (await tool(served.http, auth, "bots"))["content"][0]["text"] == "The org has no bots yet."
    link = await tool(served.http, auth, "connection_link", app="gmail")
    assert link["isError"] is False and "ctok_1" in link["structuredContent"]["url"]
    served.pd.accounts.append(account("apn_9"))
    found = (await tool(served.http, auth, "connections"))["structuredContent"]["connections"]
    offered = await tool(served.http, auth, "connection_tools", connection_id=found[0]["id"])
    assert [t["key"] for t in offered["structuredContent"]["tools"]] == ["gmail-send-email", "gmail-find-email"]
    assert "gmail-find-email: Find Email (ask)" in offered["content"][0]["text"]  # never set: it asks
    apps = await tool(served.http, auth, "connection_apps", q="sla")
    assert apps["structuredContent"]["apps"][0]["slug"] == "slack"
    scopes = [{"connection_id": found[0]["id"], "tools": TOOLS}]
    given = {"name": "Inbox Cat", "instructions": "Be kind.", "spec": inbox(), "skills": SKILLS, "connections": scopes}
    made = (await rpc(served.http, auth, "tools/call", name="bot_create", arguments=given))["result"]
    assert made["isError"] is False and "4 steps, 1 gates" in made["content"][0]["text"]
    assert "Inbox Cat (inbox-cat)" in (await tool(served.http, auth, "bots"))["content"][0]["text"]
    assert (await tool(served.http, auth, "bot", slug="inbox-cat"))["structuredContent"]["slug"] == "inbox-cat"
    scoped = await tool(served.http, auth, "bot_connections_set", slug="inbox-cat", connections=scopes)
    assert scoped["structuredContent"]["connections"][0]["tools"] == TOOLS

    started = await tool(served.http, auth, "bot_run", slug="inbox-cat", input="is:unread")
    assert started["isError"] is False and started["structuredContent"]["status"] == "queued"
    run_id = started["structuredContent"]["id"]
    await served.settled()
    queue = await tool(served.http, auth, "bot_approvals")
    assert "It asks: mail: use gmail-find-email. Yes? (yes, no)" in queue["content"][0]["text"]
    assert [r["id"] for r in queue["structuredContent"]["runs"]] == [run_id] and served.pd.runs == []
    await tool(served.http, auth, "bot_run_answer", run_id=run_id, answer="yes")
    await served.settled()
    got = await tool(served.http, auth, "bot_run_get", run_id=run_id)
    assert (
        "It asks: Worth answering?" in got["content"][0]["text"]
        and "answer like 1=answer 2=skip" in got["content"][0]["text"]
    )
    await tool(served.http, auth, "bot_run_answer", run_id=run_id, answer={"1": "answer", "2": "skip"})
    await served.settled()
    asked = (await tool(served.http, auth, "bot_run_get", run_id=run_id))["content"][0]["text"]
    assert "send the reply. Yes? (yes, no)" in asked and "answer like" not in asked
    cancelled = await tool(served.http, auth, "bot_run_cancel", run_id=run_id)
    assert "cancelled" in cancelled["content"][0]["text"]
    assert (await tool(served.http, auth, "bot_approvals"))["content"][0]["text"] == "No bot is waiting on you."
    modes = {"gmail-find-email": "allow", "gmail-send-email": "deny"}
    set_ = await tool(served.http, auth, "connection_permissions_set", connection_id=found[0]["id"], permissions=modes)
    assert set_["content"][0]["text"] == "Gmail ada@gmail.test: gmail-find-email allow, gmail-send-email deny."
    assert set_["structuredContent"]["permissions"] == modes
    served.pd.mail = [{"id": "m5", "subject": "Lunch again?"}]
    again = (await tool(served.http, auth, "bot_run", slug="inbox-cat", input="x"))["structuredContent"]["id"]
    await served.settled()
    await tool(served.http, auth, "bot_run_answer", run_id=again, answer="answer")
    await served.settled()
    await tool(served.http, auth, "bot_run_answer", run_id=again, answer="yes")
    await served.settled()
    blocked = (await tool(served.http, auth, "bot_run_get", run_id=again))["structuredContent"]
    assert blocked["status"] == "failed" and "gmail-send-email is blocked on the Gmail connection" in blocked["error"]
    assert [r["id"] for r in served.pd.runs] == ["gmail-find-email"] * 2  # found twice, never sent
    listed = await tool(served.http, auth, "bot_runs", slug="inbox-cat")
    assert "$0.0" in listed["content"][0]["text"] and len(listed["structuredContent"]["runs"]) == 2
    fixed = await tool(served.http, auth, "bot_run_wrong", run_id=run_id, outcome="skip", item="m1")
    assert fixed["content"][0]["text"] == "Gate worth said answer; it learned skip."
    gates = await tool(served.http, auth, "bot_gates", slug="inbox-cat")
    assert gates["content"][0]["text"] == "worth: 4 precedents"

    changed = await tool(served.http, auth, "bot_update", slug="inbox-cat", summary="Keeps the inbox")
    assert changed["structuredContent"]["summary"] == "Keeps the inbox"
    priced = (await tool(served.http, auth, "bot_models"))["content"][0]["text"]
    assert "claude-opus-5-5: $4.8/$24 per Mtok on Glyphh's key, $0.8/$4 on the org's own" in priced
    assert (await tool(served.http, auth, "bot_delete", slug="inbox-cat"))["isError"] is False
    missing = await tool(served.http, auth, "bot", slug="inbox-cat")
    assert missing["isError"] is True and missing["structuredContent"]["error"]["code"] == "E_NOT_FOUND"


async def test_a_bot_with_no_gates_on_the_orgs_own_key_and_connections_off(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    await served.http.put("/v1/bot-key", json={"key": "sk-ant-api03-the-orgs-own-key"}, headers=ada.headers)
    plain = {"name": "Poet", "instructions": "Write.", "spec": {"loop": [{"id": "poem", "agent": "A poem on $input"}]}}
    made = (await rpc(served.http, auth, "tools/call", name="bot_create", arguments=plain))["result"]
    assert made["isError"] is False, made
    assert (await tool(served.http, auth, "bot_runs", slug="poet"))["content"][0]["text"] == "No runs yet."
    run_id = (await tool(served.http, auth, "bot_run", slug="poet", input="cats"))["structuredContent"]["id"]
    await served.settled()
    said = (await tool(served.http, auth, "bot_run_get", run_id=run_id))["content"][0]["text"]
    assert "done, 1200 tokens, on the org's own key. Happy to, see you Friday." in said
    assert (await tool(served.http, auth, "bot_gates", slug="poet"))["content"][0]["text"] == "The bot has no gates."
    assert "last run done" in (await tool(served.http, auth, "bots"))["content"][0]["text"]
    async for s in serve(BOTS.model_copy(update={"pipedream_project_id": ""}), FakePipedream()):
        off = await tool(s.http, auth, "connections")
        assert off["isError"] is True and off["structuredContent"]["error"]["reason"] == "pipedream_off"
