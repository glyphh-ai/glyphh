"""The server holds a bot's permissions for its runs on a rrotor (ops/bots/approvals.py): a token of the run calling a
tool to ask about with no yes of the person's is refused (a rrotor taken over cannot act on its own), the person's
yes to the step is used once, for that tool alone; a tool its connection denies is refused and never run."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import approvals
from tests.bots.conftest import TOOLS, connected, inbox, made_bot
from tests.bots.remote import OnRrotor, online, result, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import Person, person
from tests.link import Rt

SEND: dict[str, Any] = {"question": "send: send the reply. Yes?", "options": ["yes", "no"], "step": "send"}


async def _out(r: OnRrotor, engine: AsyncEngine, **modes: str) -> tuple[Person, Rt, str, str]:
    """A run of the inbox bot out on its rrotor, its Gmail tools asking the person (or as `modes` set them)."""
    ada = await person(engine)
    rt = await online(engine, ada)
    gmail = await connected(r.s, ada, allow=False)
    if modes:
        put = await r.s.http.put(
            f"/v1/connections/{gmail['id']}/permissions", json={"permissions": modes}, headers=ada.headers
        )
        assert put.status_code == 200, put.text
    scopes = [{"connection_id": gmail["id"], "tools": TOOLS}]
    await made_bot(r.s, ada, runs_on=str(rt.id), connections=scopes, spec=inbox())
    run = (await r.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    return ada, rt, run["id"], r.hub.last().inputs["tool_token"]


async def _call(r: OnRrotor, run_id: str, token: str, tool: str) -> Any:
    headers = {"authorization": f"Bearer {token}"}
    res = await r.s.http.post(f"/v1/bots/runs/{run_id}/tool", json={"tool": tool, "input": {}}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _refused(tool: str) -> dict[str, str]:
    return {"error": approvals.UNAPPROVED.format(tool=tool)}


async def _asked(r: OnRrotor, rt: Rt, who: Person, run_id: str, answer: str) -> None:
    await r.landed(rt, who, uuid.UUID(run_id), result("needs_input", approval=True, **SEND))
    res = await r.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": answer}, headers=who.headers)
    assert res.status_code == 202 and res.json()["status"] == "dispatched", res.text


async def test_a_run_token_calling_a_tool_to_ask_about_with_no_yes_is_refused(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    _, _, run_id, token = await _out(on_rrotor, engine)
    for tool in TOOLS:  # the rrotor's guard skipped: the server refuses, Pipedream is never called
        assert await _call(on_rrotor, run_id, token, tool) == _refused(tool)
    assert on_rrotor.s.pd.runs == []


async def test_the_persons_yes_runs_that_tool_once_and_no_other(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, run_id, token = await _out(on_rrotor, engine)
    await _asked(on_rrotor, rt, ada, run_id, "yes")
    assert await _call(on_rrotor, run_id, token, "gmail-find-email") == _refused("gmail-find-email")
    assert "result" in await _call(on_rrotor, run_id, token, "gmail-send-email")
    assert [p["id"] for p in on_rrotor.s.pd.runs] == ["gmail-send-email"]
    assert await _call(on_rrotor, run_id, token, "gmail-send-email") == _refused("gmail-send-email")  # used up
    await _asked(on_rrotor, rt, ada, run_id, "no")
    assert await _call(on_rrotor, run_id, token, "gmail-send-email") == _refused("gmail-send-email")


async def test_a_tool_its_connection_denies_is_refused_and_one_it_allows_runs(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    modes = {"gmail-send-email": "deny", "gmail-find-email": "allow"}
    _, _, run_id, token = await _out(on_rrotor, engine, **modes)
    said = await _call(on_rrotor, run_id, token, "gmail-send-email")
    assert said == {
        "error": "gmail-send-email is blocked on the Gmail connection: allow it there for the bot to use it"
    }
    assert "result" in await _call(on_rrotor, run_id, token, "gmail-find-email")
    assert [p["id"] for p in on_rrotor.s.pd.runs] == ["gmail-find-email"]


def test_only_a_yes_to_an_approval_of_a_tool_step_is_kept() -> None:
    spec = inbox(loop=[*inbox()["loop"], {"id": "page", "run": "fetch", "input": "https://x.test", "approval": "go"}])
    who = uuid.uuid4()
    kept = approvals.granted({**SEND, "approval": True}, spec, "yes", who)
    assert list(kept) == ["gmail-send-email"] and kept["gmail-send-email"]["by"] == str(who)
    assert approvals.granted({**SEND, "approval": True}, spec, "yes", None)["gmail-send-email"]["by"] is None
    assert approvals.granted({**SEND, "approval": True}, spec, "no", who) == {}
    assert approvals.granted(SEND, spec, "yes", who) == {}  # not an approval
    for step in ("page", "draft", "gone"):  # fetch, a step that runs no tool, no such step
        assert approvals.granted({**SEND, "step": step, "approval": True}, spec, "yes", who) == {}
