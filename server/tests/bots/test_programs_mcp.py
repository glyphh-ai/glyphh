"""Programs through the connector (docs/specs/programs.md, 6), as Claude calls them: a program saved from its steps,
read, scheduled, run with `run_program` (each line of its trail streamed as a progress notification to a client that
asks, then the run as it stands), answered, cancelled, deleted; `search_tool` finding tools and giving one to a bot."""

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request
from starlette.responses import Response

from glyphh_server.api import mcp_stream
from glyphh_server.mcp import protocol
from glyphh_server.mcp.tools import program_runs
from tests.bots.conftest import Served, made_bot
from tests.bots.market import linked
from tests.bots.programs import FIND_STEP
from tests.connector import UI, granted, modern, modern_headers, rpc, tool
from tests.db.helpers import person

FLOW: list[dict[str, Any]] = [
    {**FIND_STEP, "next": "ask"},
    {"id": "ask", "kind": "ask", "question": "Reply to {input}?", "options": ["Yes", "No"], "next": None},
]


async def save(s: Served, auth: dict[str, str], **given: Any) -> dict[str, Any]:
    return dict((await rpc(s.http, auth, "tools/call", name="program_save", arguments=given))["result"])


def text(got: dict[str, Any]) -> str:
    return str(got["content"][0]["text"])


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(program_runs, "EVERY", 0.01)


async def test_a_program_is_saved_run_followed_and_answered_through_the_connector(
    served: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    await made_bot(served, ada)
    assert text(await tool(served.http, auth, "programs")) == "No programs yet."
    saved = await save(served, auth, name="Mail Round", flow=FLOW, bot="inbox-cat")
    assert saved["isError"] is False, saved
    assert text(saved) == "Saved. mail-round: Mail Round, 2 steps on Glyphh cloud; Off"
    half = await tool(served.http, auth, "program_save", slug="mail-round", flow=[{"id": "a", "kind": "ask"}])
    assert text(half).endswith("It cannot run yet: a: a ask step needs its question")
    refused = await tool(served.http, auth, "run_program", slug="mail-round")
    assert refused["isError"] is True and "cannot run yet" in text(refused)
    await tool(served.http, auth, "program_save", slug="mail-round", flow=FLOW)
    got = await tool(served.http, auth, "program_get", slug="mail-round")
    assert "FLOW = [" in text(got) and got["structuredContent"]["flow"] == FLOW
    assert text(await tool(served.http, auth, "programs", q="mail")).startswith("mail-round: Mail Round, 2 steps")
    timed = await tool(served.http, auth, "program_schedule", slug="mail-round", every="day", at="08:00")
    assert text(timed).startswith("mail-round: Every day at 8:00") and timed["structuredContent"]["next_run_at"]
    off = await tool(served.http, auth, "program_schedule", slug="mail-round", every="off")
    assert text(off) == "mail-round: Off; next never."

    ran = await tool(served.http, auth, "run_program", slug="mail-round", input="lunch")
    assert ran["isError"] is False, ran
    run = ran["structuredContent"]
    assert (run["status"], run["trigger"]) == ("needs_input", "connector")
    assert [e["kind"] for e in run["events"]] == ["started", "step", "asked"]
    assert text(ran).splitlines()[1] == "step find (inbox-cat) gmail find email: Find Email"
    assert text(ran).endswith(f"Run {run['id']} of mail-round waits: Reply to lunch? (Yes, No); program_run_answer")
    assert "waits: Reply to lunch?" in text(await tool(served.http, auth, "program_runs", slug="mail-round"))
    on = await tool(served.http, auth, "program_run_answer", run_id=run["id"], answer="Yes")
    assert on["isError"] is False and "carries on" in text(on)
    await served.settled()
    done = await tool(served.http, auth, "program_run_get", run_id=run["id"])
    assert done["structuredContent"]["status"] == "done" and "is done. Results: {" in text(done)
    assert "answered ask (Ada Lovelace): Yes" in text(done)

    monkeypatch.setattr(program_runs, "FOLLOW", 0.0)  # it stops following: the run as it stands, still going
    going = await tool(served.http, auth, "run_program", slug="mail-round", input="tea")
    assert f"of mail-round is {going['structuredContent']['status']} at " in text(going)
    assert "program_run_get follows it" in text(going)
    await served.settled()
    stopped = await tool(served.http, auth, "program_run_cancel", run_id=going["structuredContent"]["id"])
    assert text(stopped).endswith("cancelled.")
    failed = await tool(served.http, auth, "program_runs", slug="mail-round")
    assert "failed: cancelled" in text(failed)
    gone = await tool(served.http, auth, "program_delete", slug="mail-round")
    assert text(gone) == "Program mail-round deleted, with its runs."
    assert text(await tool(served.http, auth, "program_runs", slug="mail-round")) == "There is no such program."


async def test_run_program_streams_each_step_as_it_goes(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    await made_bot(served, ada)
    await save(served, auth, name="Mail Round", flow=FLOW, bot="inbox-cat")
    body = modern("tools/call", {"name": "run_program", "arguments": {"slug": "mail-round", "input": "lunch"}}, UI)
    body["params"]["_meta"]["progressToken"] = "p1"
    headers = modern_headers(body, auth) | {"accept": "application/json, text/event-stream"}
    res = await served.http.post("/mcp", json=body, headers=headers)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/event-stream")
    sent = [json.loads(f.split("data: ", 1)[1]) for f in res.text.strip().split("\n\n")]
    assert [m.get("method") for m in sent] == ["notifications/progress"] * 3 + [None]
    assert [m["params"] for m in sent[:3]] == [
        {"progressToken": "p1", "progress": 1, "message": "started (Ada Lovelace): connector"},
        {"progressToken": "p1", "progress": 2, "message": "step find (inbox-cat) gmail find email: Find Email"},
        {"progressToken": "p1", "progress": 3, "message": "asked ask Reply to lunch?"},
    ]
    assert sent[3]["id"] == 1 and sent[3]["result"]["structuredContent"]["status"] == "needs_input"
    plain = await served.http.post("/mcp", json=body, headers=modern_headers(body, auth))  # no stream asked for
    assert plain.headers["content-type"] == "application/json" and plain.json()["result"]["isError"] is True


def _request(accept: str) -> Request:
    return Request({"type": "http", "headers": [(b"accept", accept.encode())]})


def _call(name: str, token: Any = "p") -> protocol.Call:
    return protocol.Call(1, "tools/call", {"name": name, "_meta": {"progressToken": token}}, protocol.MODERN)


async def test_only_a_followed_tool_asked_for_as_a_stream_is_streamed() -> None:
    sse = _request("text/event-stream")
    assert mcp_stream.token(sse, _call("run_program")) == "p" and mcp_stream.token(sse, _call("run_program", 7)) == 7
    assert mcp_stream.token(sse, _call("programs")) is None
    assert mcp_stream.token(_request("application/json"), _call("run_program")) is None
    assert mcp_stream.token(sse, _call("run_program", True)) is None
    assert mcp_stream.token(sse, protocol.Call(1, "tools/list", {}, protocol.MODERN)) is None

    async def crashes(ctx: Any, call: protocol.Call) -> Response:
        await ctx.progress("one")
        raise RuntimeError("boom")

    from tests.bots.agents import SESSION  # any hashable stand-in for the frozen context's fields

    ctx = program_runs.Context(None, None, None, None, None, None, SESSION)  # type: ignore[arg-type]
    stream = mcp_stream.stream(ctx, _call("run_program"), "p", crashes)
    frames = [json.loads(f.split("data: ", 1)[1]) async for f in stream.body_iterator]  # type: ignore[union-attr]
    assert frames[0]["params"]["message"] == "one"
    assert frames[1] == {"jsonrpc": "2.0", "error": {"code": -32603, "message": "The call failed."}, "id": 1}


async def test_search_tool_finds_tools_and_gives_one_to_a_bot(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    bot = await made_bot(served, ada, connections=[], spec={})
    await linked(served, ada, "gmail")
    found = await tool(served.http, auth, "search_tool", q="email", bot=bot["slug"])
    assert text(found).splitlines() == [
        "Gmail: Send Email (gmail-send-email)",
        "Gmail: Find Email (gmail-find-email, reads only)",
    ]
    assert text(await tool(served.http, auth, "search_tool", q="zebra")) == "No tool has those words."
    many = await tool(served.http, auth, "search_tool", q="email", add_to=bot["slug"])
    assert many["isError"] is True and text(many) == "2 tools have those words: name the one to add exactly."
    added = await tool(served.http, auth, "search_tool", q="gmail-find-email", add_to=bot["slug"])
    assert text(added) == "inbox-cat can now use Find Email (Gmail)." and added["structuredContent"]["added"]
    has = await tool(served.http, auth, "search_tool", q="find", bot=bot["slug"])
    assert text(has) == "Gmail: Find Email (gmail-find-email, reads only, the bot has it)"
