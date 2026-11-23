"""A bot's use of the files in its folders, on its rrotor (docs/specs/bots.md, 14; ops/bots/files.py): which rrotors
are told to give its agent steps those files, the server's word on each change (`file_change`: at once, or by the
person's yes to that very change, once), and what is kept with the run: the names of the files it read and changed,
and nothing of what is in them."""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Rrotor
from glyphh_server.ops.bots import approvals, files, said, tool_calls
from glyphh_server.ops.link.protocol import Call, Continue
from tests.bots.conftest import made_bot
from tests.bots.remote import OnRrotor, online, result, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import Person, person

DOCS: dict[str, str] = {"path": "/Users/ana/Invoices", "access": "read"}
NOTES: dict[str, str] = {"path": "/Users/ana/Notes", "access": "write"}
KEPT: dict[str, str] = {"path": "/Users/ana/Notes/kept", "access": "read"}
SPEC: dict[str, Any] = {"loop": [{"id": "work", "agent": "Do your filing."}]}
FILER: dict[str, Any] = {
    "name": "Filer",
    "summary": "Keeps the invoices in order",
    "instructions": "File.",
    "spec": SPEC,
}
WRITE: dict[str, str] = {"action": "write", "path": "/Users/ana/Notes/Summary.md", "name": "Notes/Summary.md"}
MOVE: dict[str, str] = {
    "action": "move",
    "path": "/Users/ana/Notes/a.txt",
    "name": "Notes/a.txt",
    "to": "/Users/ana/Notes/done/a.txt",
    "to_name": "Notes/done/a.txt",
}
ASK: dict[str, Any] = {"question": "Write Notes/Summary.md?", "options": ["yes", "no"], "approval": True}


async def _on(r: OnRrotor, engine: AsyncEngine, version: str | None = "0.8.0", **over: Any) -> tuple[Person, Any, Any]:
    ada = await person(engine)
    rt = await online(engine, ada)
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(image_version=version))
    await made_bot(r.s, ada, runs_on=str(rt.id), **{**FILER, "folders": [DOCS, NOTES, KEPT], **over})
    task = {"input": "Summarise my invoices"}
    run = await r.s.http.post("/v1/bots/filer/runs", json=task, headers=ada.headers)
    assert run.status_code == 202, run.text
    return ada, rt, run.json()


def _with(base: dict[str, Any], **data: Any) -> dict[str, Any]:
    """A rrotor's Result with what glyphh_bot adds beside the runner's own: the files named, the change asked about."""
    return {**base, "data": {**base["data"], **data}}


async def _change(r: OnRrotor, run_id: str, given: Any) -> Any:
    call = next(sent for _, sent in reversed(r.hub.sent) if isinstance(sent, Call))  # the run's last call: its token
    headers = {"authorization": f"Bearer {call.inputs['tool_token']}"}
    body = {"tool": "file_change", "input": given}
    res = await r.s.http.post(f"/v1/bots/runs/{run_id}/tool", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


async def _run(r: OnRrotor, who: Person, run_id: str) -> dict[str, Any]:
    return dict((await r.s.http.get(f"/v1/bot-runs/{run_id}", headers=who.headers)).json())


# Which rrotors


def test_which_rrotors_give_a_bot_its_folders_files() -> None:
    assert [files.uses(v) for v in ("0.8.0", "0.8.1-rc1", "0.10.2", "1.0.0")] == [True] * 4
    assert [files.uses(v) for v in ("0.7.0", "0.6.9", "", None, "latest")] == [False] * 5


async def test_a_rrotor_new_enough_is_told_to_give_the_bot_its_files(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    _, _, run = await _on(on_rrotor, engine)
    sent = on_rrotor.hub.last()
    assert isinstance(sent, Call) and run["status"] == "dispatched" and sent.folders == [DOCS, NOTES, KEPT]
    assert sent.inputs["file_tools"] is True and sent.inputs["given"] == "Summarise my invoices"


@pytest.mark.parametrize(("version", "over"), [("0.7.0", {}), ("0.8.0", {"folders": []})])
async def test_an_older_rrotor_or_a_bot_with_no_folders_keeps_the_single_request(
    on_rrotor: OnRrotor, engine: AsyncEngine, version: str, over: dict[str, Any]
) -> None:
    ada, rt, run = await _on(on_rrotor, engine, version, **over)
    sent = on_rrotor.hub.last()
    assert run["status"] == "dispatched" and "file_tools" not in sent.inputs
    # and its typed task still gets the hint: nothing read it
    await on_rrotor.landed(rt, ada, uuid.UUID(run["id"]), result(output="Filed."))
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["hint"].startswith("Filer does one job") and ended["files"] == []
    assert "_files" not in ended["data"]


# The server's word on a change


async def test_a_bot_that_acts_on_its_own_may_change_at_once_within_its_folders(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _on(on_rrotor, engine, permission_mode="auto")
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": True}}
    assert await _change(on_rrotor, run["id"], MOVE) == {"result": {"allowed": True}}
    for path in ("/Users/ana/Invoices/x.txt", "/Users/ana/Notes/kept/x.txt", "/etc/passwd", "/Users/ana/Notes/../x"):
        said_no = await _change(on_rrotor, run["id"], {**WRITE, "path": path})
        assert said_no == {"error": files.NO_FOLDERS.format(path=path, name="Filer")}
    outside = await _change(on_rrotor, run["id"], {**MOVE, "to": "/Users/ana/Invoices/a.txt"})
    assert outside["error"].startswith("/Users/ana/Invoices/a.txt is not in a folder Filer may change")
    for bad in (None, "x", {"action": "delete", **{k: v for k, v in WRITE.items() if k != "action"}}):
        assert await _change(on_rrotor, run["id"], bad) == {"error": files.BAD}
    await on_rrotor.landed(rt, ada, uuid.UUID(run["id"]), result())
    assert await _change(on_rrotor, run["id"], WRITE) == {"error": tool_calls.NOT_OUT}


async def test_a_bot_that_asks_first_changes_only_by_the_persons_yes_to_that_change_once(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _on(on_rrotor, engine)
    run_id = uuid.UUID(run["id"])
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": False}}  # the rrotor asks
    seen = [{"name": "Invoices/March.pdf", "did": "read"}]
    await on_rrotor.landed(rt, ada, run_id, _with(result("needs_input", **ASK), file=WRITE, files=seen))
    waiting = await _run(on_rrotor, ada, run["id"])
    assert waiting["status"] == "needs_input" and waiting["question"]["question"] == "Write Notes/Summary.md?"
    assert waiting["question"]["approval"] is True and waiting["question"]["options"] == ["yes", "no"]
    assert waiting["files"] == seen and waiting["hint"] == ""
    res = await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "yes"}, headers=ada.headers)
    assert res.status_code == 202 and isinstance(on_rrotor.hub.last(), Continue)
    # the yes is to that change alone, and is used up by it
    assert await _change(on_rrotor, run["id"], MOVE) == {"result": {"allowed": False}}
    assert await _change(on_rrotor, run["id"], {**WRITE, "path": "/Users/ana/Notes/Other.md"}) == {
        "result": {"allowed": False}
    }
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": True}}
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": False}}
    # a move, asked and answered the same way; a no keeps nothing
    await on_rrotor.landed(rt, ada, run_id, _with(result("needs_input", **ASK), file=MOVE, files=[]))
    await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "yes"}, headers=ada.headers)
    assert await _change(on_rrotor, run["id"], {**MOVE, "to": "/Users/ana/Notes/else.txt"}) == {
        "result": {"allowed": False}
    }
    assert await _change(on_rrotor, run["id"], MOVE) == {"result": {"allowed": True}}
    await on_rrotor.landed(rt, ada, run_id, _with(result("needs_input", **ASK), file=WRITE, files=[]))
    await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "no"}, headers=ada.headers)
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": False}}


def test_a_yes_to_a_change_is_kept_as_the_yes_to_that_change() -> None:
    who = uuid.uuid4()
    kept = approvals.granted({**ASK, "step": None, "file": MOVE}, SPEC, "yes", who)
    assert list(kept) == ["file_change"] and kept["file_change"]["by"] == str(who)
    assert {k: kept["file_change"][k] for k in MOVE} == MOVE
    assert approvals.granted({**ASK, "file": MOVE}, SPEC, "no", who) == {}
    assert approvals.granted({**ASK, "approval": False, "file": MOVE}, SPEC, "yes", who) == {}
    assert approvals.granted({**ASK, "step": "work", "file": {"action": "delete"}}, SPEC, "yes", who) == {}


# What is kept with the run


async def test_a_run_keeps_the_names_of_its_files_and_the_turn_shows_them(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _on(on_rrotor, engine)
    run_id = uuid.UUID(run["id"])
    read = [{"name": "Invoices/March.pdf", "did": "read"}, {"name": "Invoices/April.pdf", "did": "read"}]
    junk = [{"name": "x", "did": "deleted"}, {"name": 7, "did": "read"}, "y", {"name": "z", "did": "read", "text": "!"}]
    await on_rrotor.landed(rt, ada, run_id, _with(result("needs_input", **ASK), file=WRITE, files=[*read, *junk]))
    await on_rrotor.landed(rt, ada, run_id, {"status": "expired", "step": "wait", "data": {}})
    await on_rrotor.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": "yes"}, headers=ada.headers)
    fresh = on_rrotor.hub.last()  # the wait expired there: a fresh call, the task with it again
    assert isinstance(fresh, Call) and fresh.inputs["answer"] == "yes" and fresh.inputs["file_tools"] is True
    assert fresh.inputs["given"] == "Summarise my invoices"
    # the fresh call starts the step again: what it names is added to what the run had
    after = [{"name": "Invoices/March.pdf", "did": "read"}, {"name": "Notes/Summary.md", "did": "written"}]
    done = _with(result(output="Summarised in **Summary.md**.", data={"work": "Summarised."}), files=after)
    await on_rrotor.landed(rt, ada, run_id, done)
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["status"] == "done" and ended["question"] is None
    assert ended["files"] == [  # what it changed first
        {"name": "Notes/Summary.md", "did": "written"},
        {"name": "Invoices/April.pdf", "did": "read"},
        {"name": "z", "did": "read"},
        {"name": "Invoices/March.pdf", "did": "read"},
    ]
    assert ended["data"] == {"work": "Summarised.", "_files": [read[1], {"name": "z", "did": "read"}, *after]}
    assert ended["hint"] == ""  # the task was read by its step: no "it does not read what you type"
    assert ended["links"] == [] and ended["apps"] == []


def test_the_changes_a_rrotor_may_name() -> None:
    assert files.change(WRITE) == WRITE and files.change(MOVE) == MOVE
    assert files.change({**WRITE, "more": "x"}) == WRITE
    for bad in (
        {**WRITE, "path": ""},
        {**WRITE, "name": None},
        {**WRITE, "path": "x" * 1101},
        {**WRITE, "path": "/a\x00b"},
        {**WRITE, "to": "/Users/ana/Notes/b", "to_name": "Notes/b"},  # a write goes nowhere
        {k: v for k, v in MOVE.items() if k != "to_name"},
        {**MOVE, "to": 7},
        {**MOVE, "action": "copy"},
    ):
        assert files.change(bad) is None, bad


def test_the_files_kept_and_shown_and_whether_a_run_had_them() -> None:
    many = [{"name": f"f{n}", "did": "read"} for n in range(300)]
    assert files.named(None) is None and files.named({}) is None and files.named([]) == []
    assert len(files.named(many) or []) == 200 and len(files.merged(many, many[:5])) == 200
    assert files.merged("junk", many[:2]) == many[:2]
    run = SimpleNamespace(data={"_files": many}, input="x", status="done", error="")
    assert len(files.of(run)) == 12 and files.of(SimpleNamespace(data=None)) == []
    assert files.used(run, SPEC) and not files.used(run, {"loop": [{"id": "a", "run": "fetch"}, "junk"]})
    assert not files.used(SimpleNamespace(data=None), SPEC) and not files.used(run, {})
    assert said.hint(run, SPEC, "Filer", "Files") == ""
    assert said.hint(SimpleNamespace(data={}, input="x", status="done", error=""), SPEC, "Filer", "Files") != ""
