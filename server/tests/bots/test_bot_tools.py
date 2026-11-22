"""A bot's own tools in the org's connector (ops/bots/exposed.py, mcp/tools/bot_tools.py): declared by purpose, listed
by their names (a taken name gets the bot's slug after it), each calling its bot: a run on its arguments answered with
its verdicts, its runs, a gate's verdict corrected, a waiting run answered; declarations that do not fit are refused,
and every template's fits its bot."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import exposed, templates
from tests.bots.conftest import Served, made_bot
from tests.connector import granted, rpc, tool
from tests.db.helpers import person

DECLARED: list[dict[str, Any]] = [
    {"name": "check_mail", "title": "Check the mail", "description": "Find the mail worth answering", "op": "run",
     "args": {"query": "A Gmail search", "note": "Why"}, "required": ["query"], "given": "query", "verdicts": "worth",
     "wait": 5},
    {"name": "check_all", "description": "Every mail, its arguments as JSON", "op": "run", "args": {"query": "q"}},
    {"name": "mail_runs", "description": "The mail it went through", "op": "runs", "verdicts": "worth"},
    {"name": "correct", "description": "A verdict was wrong", "op": "wrong", "gate": "worth"},
    {"name": "bots", "description": "Its answer to a waiting run (a server tool's name)", "op": "answer"},
]  # fmt: skip


async def test_a_bots_tools_are_listed_and_run_it(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    await made_bot(served, ada, connector_tools=DECLARED)
    listed = {t["name"]: t for t in (await rpc(served.http, auth, "tools/list"))["result"]["tools"]}
    assert {"check_mail", "check_all", "mail_runs", "correct", "bots__inbox-cat", "bots"} <= set(listed)
    assert listed["check_mail"]["description"] == "Find the mail worth answering (the Inbox Cat bot)"
    assert (
        listed["check_mail"]["inputSchema"]["required"] == ["query"]
        and listed["mail_runs"]["annotations"]["readOnlyHint"]
    )
    ran = await tool(served.http, auth, "check_mail", query="is:unread")
    assert ran["isError"] is False and ran["structuredContent"]["status"] == "needs_input", ran
    run_id = ran["structuredContent"]["run_id"]
    assert "is:unread" in str(served.pd.runs[-1]) and ran["structuredContent"]["question"]["batch"]
    said = await tool(served.http, auth, "bots__inbox-cat", run_id=run_id, answer={"1": "answer", "2": "skip"})
    assert said["isError"] is False and "carries on" in said["content"][0]["text"]
    await served.settled()
    runs = (await tool(served.http, auth, "mail_runs"))["structuredContent"]["runs"]
    assert runs[0]["run_id"] == run_id and runs[0]["verdicts"] and runs[0]["question"]["approval"] is True
    await tool(served.http, auth, "bot_run_cancel", run_id=run_id)
    fixed = await tool(served.http, auth, "correct", run_id=run_id, outcome="skip", item="m1")
    assert fixed["content"][0]["text"] == "Gate worth said answer; it learned skip.", fixed
    at_once = await tool(served.http, auth, "check_all", query="x")
    assert at_once["structuredContent"]["status"] == "queued" and "verdicts" not in at_once["structuredContent"]
    await served.settled()
    failed = (await tool(served.http, auth, "mail_runs"))["structuredContent"]["runs"]
    assert failed[1]["error"] == "cancelled"


async def test_a_bots_tool_takes_only_its_own_runs(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    await made_bot(served, ada, connector_tools=DECLARED)
    poet = {"name": "Poet", "instructions": "Write.", "spec": {"loop": [{"id": "poem", "agent": "A poem on $input"}]}}
    assert (await served.http.post("/v1/bots", json=poet, headers=ada.headers)).status_code == 201
    run_id = (await tool(served.http, auth, "bot_run", slug="poet", input="cats"))["structuredContent"]["id"]
    await served.settled()
    for name, args in (("correct", {"outcome": "skip"}), ("bots__inbox-cat", {"answer": "yes"})):
        said = await tool(served.http, auth, name, run_id=run_id, **args)
        assert (
            said["isError"] is True
            and said["structuredContent"]["error"]["message"] == "That run is not one of this bot's."
        )
    missing = await rpc(served.http, auth, "tools/call", name="no_such_tool", arguments={})
    assert "There is no tool 'no_such_tool'." in missing["error"]["message"]


async def test_declarations_that_do_not_fit_the_bot_are_refused(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    bad = [
        {"name": "a", "description": "x", "op": "run", "args": {"Bad": "x"}, "required": ["gone"], "given": "nope",
         "verdicts": "nope"},
        {"name": "a", "description": "x", "op": "runs", "args": {"q": "x"}},
        {"name": "glyphh_b", "description": "x", "op": "wrong"},
    ]  # fmt: skip
    with pytest.raises(Invalid) as err:
        exposed.check({"loop": [{"id": "s"}], "gates": {}}, bad)
    assert err.value.detail["problems"] == [
        "a: two tools have this name",
        "a: argument Bad is not a lowercase name",
        "a: required gone is not one of its args",
        "a: given nope is not one of its args",
        "a: verdicts nope is not a step of the loop",
        "a: only a run takes args (the other ops' arguments are fixed)",
        "glyphh_b: its name may not begin glyphh_",
        "glyphh_b: a wrong corrects one of the bot's gates: name it as gate",
    ]
    poem = {"loop": [{"id": "p", "agent": "A poem"}]}
    made = {"name": "X", "instructions": "x", "spec": poem, "connector_tools": bad[2:]}
    res = await served.http.post("/v1/bots", json=made, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "connector_tools"
    for t in templates.library().values():  # every template's tools fit its bot
        exposed.check(t.spec, [c.model_dump() for c in t.connector_tools])
