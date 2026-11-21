"""The bots' edges: Pipedream failing every way it can, a run's Claude failing, Ada's tools, two accounts of one app,
a connection gone since it was scoped, the real Claude client, and a run cut off by the server stopping."""

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.errors import Invalid, Unavailable
from glyphh_server.ops.bots import props, tools
from glyphh_server.ops.bots.pipedream import Pipedream
from tests.bots.conftest import BOTS, Served, connected, made_bot, serve
from tests.bots.fakes import FakePipedream, reply, text, use
from tests.bots.test_runs import SEND_ARGS, ran, scoped
from tests.connector import granted, tool
from tests.db.helpers import person


async def test_pipedream_down_or_unreachable_is_unavailable_and_a_refusal_invalid(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    gmail = await connected(served, ada)
    for mode, status in (("down", 503), ("broken", 503), ("refusing", 422)):
        served.pd.mode = mode
        res = await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ada.headers)
        assert res.status_code == status, (mode, res.text)
    served.pd.mode = ""
    served.pd.accounts = []  # gone at Pipedream already: deleting it here still works
    assert (await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ada.headers)).status_code == 204


async def test_pipedream_off_refuses_before_any_call() -> None:
    pd = Pipedream(httpx.AsyncClient(), Settings(secret_key="x" * 32))
    with pytest.raises(Unavailable):
        await pd.apps(None, None)


def test_an_action_without_an_app_prop_is_run_with_the_callers_values_only() -> None:
    defined = [{"name": "q", "type": "string"}]
    assert props.configured(defined, "apn_1", {"q": "x", "other": 1}) == {"q": "x"}


def test_a_tool_name_taken_twice_is_made_unique() -> None:
    offered = tools.Offered()

    async def call(_: dict[str, Any]) -> Any:
        return None

    for _ in range(3):
        offered.add("tool", "gmail-send-email", "Send", {"type": "object"}, call)
    assert list(offered.calls) == ["gmail-send-email", "gmail-send-email-2", "gmail-send-email-3"]


async def test_a_tool_answering_garbage_is_an_error_and_a_run_whose_tools_fail_to_load_fails(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    await scoped(served, ada)
    served.pd.mode = "garbled"
    served.claude.replies = [reply(use("gmail-send-email", SEND_ARGS), stop="tool_use"), reply(text("Hm."))]
    run = await ran(served, ada)
    assert run["status"] == "done" and run["steps"][0]["is_error"] is True
    assert "JSONDecodeError" in run["steps"][0]["output"]["error"]
    served.pd.mode = "down"
    run = await ran(served, ada)
    assert run["status"] == "failed" and run["error"].startswith("Its tools could not be read: Pipedream failed")


async def test_a_run_whose_claude_fails_is_failed_saying_why(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    served.claude.raises = Invalid("The org is out of tokens.")
    assert (await ran(served, ada))["error"] == "The org is out of tokens."
    served.claude.raises = RuntimeError("socket closed")
    assert (await ran(served, ada))["error"] == "The run failed: RuntimeError: socket closed"


async def test_a_bot_asks_and_teaches_only_its_ada_models(
    served: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[tuple[str, str, dict[str, Any]]] = []

    async def ask(state: Any, who: Any, model: str, op: str, args: dict[str, Any]) -> Any:
        asked.append((model, op, args))
        return {"answer": "spam", "confidence": 0.9} if op == "decide" else {"id": "c1", "precedents": 2}

    monkeypatch.setattr(tools, "ask", ask)
    served.app.state.bots.ada = object()  # Ada Cloud on, as far as the bot's tools know
    ada = await person(engine)
    await made_bot(served, ada, models=["triage"])
    served.claude.replies = [
        reply(
            use("ada_decide", {"model": "triage", "data": {"subject": "Win"}}, "tu_1"),
            use("ada_record", {"model": "triage", "data": {"subject": "Win"}, "outcome": "spam"}, "tu_2"),
            use("ada_decide", {"model": "payroll", "data": {}}, "tu_3"),
            stop="tool_use",
        ),
        reply(text("It is spam.")),
    ]
    run = await ran(served, ada)
    assert [(s["kind"], s["name"], s["is_error"]) for s in run["steps"][:3]] == [
        ("ada", "ada_decide", False),
        ("ada", "ada_record", False),
        ("ada", "ada_decide", True),
    ]
    assert asked == [
        ("triage", "decide", {"data": {"subject": "Win"}}),
        ("triage", "record", {"data": {"subject": "Win"}, "outcome": "spam"}),
    ]
    offered = served.claude.requests[0]["tools"]
    assert [t["name"] for t in offered] == ["ada_decide", "ada_record"]
    assert offered[0]["input_schema"]["properties"]["model"]["enum"] == ["triage"]


async def test_two_accounts_of_one_app_and_a_connection_gone_since(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    first, second = await connected(served, ada, "apn_1"), await connected(served, ada, "apn_2")
    both = [{"connection_id": c["id"], "tools": ["gmail-send-email"]} for c in (first, second)]
    res = await served.http.put("/v1/bots/inbox-cat/connections", json={"connections": both}, headers=ada.headers)
    assert res.status_code == 200
    await ran(served, ada)
    assert [t["name"] for t in served.claude.requests[-1]["tools"]] == ["gmail-send-email", "gmail-send-email-2"]
    served.pd.accounts = [a for a in served.pd.accounts if a["id"] == "apn_2"]
    await served.http.post("/v1/connections/sync", headers=ada.headers)
    await ran(served, ada)
    assert [t["name"] for t in served.claude.requests[-1]["tools"]] == ["gmail-send-email"]
    bot = (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).json()
    assert [c["connection_id"] for c in bot["connections"]] == [second["id"]]


async def test_names_without_a_letter_a_new_look_and_a_missing_run(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    assert (await served.http.post("/v1/bots", json={"name": "!!!"}, headers=ada.headers)).status_code == 422
    await made_bot(served, ada)
    res = await served.http.patch("/v1/bots/inbox-cat", json={"look": {"eye": "big"}}, headers=ada.headers)
    assert res.json()["look"] == {"eye": "big"}
    assert (await served.http.get(f"/v1/bot-runs/{uuid.uuid4()}", headers=ada.headers)).status_code == 404


async def test_the_connector_lists_and_reads_bots_and_says_when_connections_are_off(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    assert (await tool(served.http, auth, "bots"))["content"][0]["text"] == "The org has no bots yet."
    await made_bot(served, ada)
    assert "Inbox Cat (inbox-cat)" in (await tool(served.http, auth, "bots"))["content"][0]["text"]
    assert (await tool(served.http, auth, "bot", slug="inbox-cat"))["structuredContent"]["slug"] == "inbox-cat"
    apps = await tool(served.http, auth, "connection_apps", q="sla")
    assert apps["structuredContent"]["apps"][0]["slug"] == "slack"
    async for s in serve(BOTS.model_copy(update={"pipedream_project_id": ""}), FakePipedream()):
        off = await tool(s.http, auth, "connections")
        assert off["isError"] is True and off["structuredContent"]["error"]["reason"] == "pipedream_off"


async def test_the_real_client_is_made_with_the_key_and_a_stopped_server_cuts_its_runs_off(engine: AsyncEngine) -> None:
    async for s in serve(BOTS, FakePipedream()):
        bots = s.app.state.bots
        bots.claude = None
        assert type(bots.client()).__name__ == "AsyncAnthropic" and bots.client() is bots.client()
        fake = s.claude
        bots.claude = fake
        fake.hold = asyncio.Event()
        ada = await person(engine)
        await made_bot(s, ada)
        res = await s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)
        while not fake.requests:
            await asyncio.sleep(0.01)
    assert fake.closed and not bots.tasks
    async for s in serve(BOTS, FakePipedream()):
        run = (await s.http.get(f"/v1/bot-runs/{res.json()['id']}", headers=ada.headers)).json()
        assert run["status"] == "failed" and run["error"] == "interrupted by a restart"
