"""A bot's use of the files in its folders, on its rrotor (docs/specs/bots.md, 14; ops/bots/files.py): each call
carries the folders and tells the rrotor to give the agent its file tools, the server's word on each change
(`file_change`: at once, or by the person's yes to that very change, once), and what is kept with the run: the names
of the files it read and changed, and nothing of what is in them."""

import uuid
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import approvals, files, tool_calls
from glyphh_server.ops.link.protocol import Call, Continue
from tests.bots.remote import EXPIRED, OnRrotor, left, out, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import Person
from tests.link import Rt

DOCS: dict[str, str] = {"path": "/Users/ana/Invoices", "access": "read"}
NOTES: dict[str, str] = {"path": "/Users/ana/Notes", "access": "write"}
KEPT: dict[str, str] = {"path": "/Users/ana/Notes/kept", "access": "read"}
FILER: dict[str, Any] = {
    "name": "Filer",
    "summary": "Keeps the invoices in order",
    "instructions": "File.",
    "spec": {},
    "folders": [DOCS, NOTES, KEPT],
}
WRITE: dict[str, str] = {"action": "write", "path": "/Users/ana/Notes/Summary.md", "name": "Notes/Summary.md"}
MOVE: dict[str, str] = {
    "action": "move",
    "path": "/Users/ana/Notes/a.txt",
    "name": "Notes/a.txt",
    "to": "/Users/ana/Notes/done/a.txt",
    "to_name": "Notes/done/a.txt",
}
ASKS: str = "Write Notes/Summary.md?"


async def _on(r: OnRrotor, engine: AsyncEngine, **over: Any) -> tuple[Person, Rt, dict[str, Any]]:
    return await out(r, engine, "Summarise my invoices", **{**FILER, **over})


def _asks(change: dict[str, str], **data: Any) -> dict[str, Any]:
    """The rrotor's Result when the server did not allow a change: it asks the person about it (agent_tools.py)."""
    return left("needs_input", ASKS, options=["yes", "no"], approval=True, file=change, **data)


async def _change(r: OnRrotor, run_id: str, given: Any) -> Any:
    return await r.tool(run_id, "file_change", given)


# With each call


async def test_a_call_carries_the_bots_folders_and_gives_it_their_files(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _on(on_rrotor, engine)
    sent = on_rrotor.hub.last()
    assert isinstance(sent, Call) and run["status"] == "dispatched" and sent.folders == [DOCS, NOTES, KEPT]
    assert sent.inputs["file_tools"] is True and sent.inputs["message"] == "Summarise my invoices"
    named = [t["name"] for t in sent.inputs["tools"]]
    assert named == ["ask_person"]  # the file tools are the machine's own: the server names none of them
    await on_rrotor.landed(rt, ada, run["id"], left(output="Nothing to file."))
    ended = await on_rrotor.run(ada, run["id"])
    assert (ended["status"], ended["files"], ended["data"]) == ("done", [], {})


async def test_a_bot_with_no_folders_is_given_no_file_tools(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, run = await _on(on_rrotor, engine, folders=[], permission_mode="auto")
    sent = on_rrotor.hub.last()
    assert run["status"] == "dispatched" and "file_tools" not in sent.inputs and sent.folders is None
    said = await _change(on_rrotor, run["id"], WRITE)  # and it may change nothing
    assert said == {"error": files.NO_FOLDERS.format(path=WRITE["path"], name="Filer")}
    done = {"status": "done", "step": None, "prompt": None, "data": {"output": "Filed."}}  # a result naming no files
    await on_rrotor.landed(rt, ada, run["id"], done)
    ended = await on_rrotor.run(ada, run["id"])
    assert (ended["output"], ended["files"]) == ("Filed.", [])


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
    await on_rrotor.landed(rt, ada, run["id"], left())
    assert await _change(on_rrotor, run["id"], WRITE) == {"error": tool_calls.NOT_OUT}


async def test_a_bot_that_asks_first_changes_only_by_the_persons_yes_to_that_change_once(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _on(on_rrotor, engine)
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": False}}  # the rrotor asks
    outside = await _change(on_rrotor, run["id"], {**WRITE, "path": "/etc/passwd"})
    assert "is not in a folder Filer may change" in outside["error"]  # never asked about
    seen = [{"name": "Invoices/March.pdf", "did": "read"}]
    await on_rrotor.landed(rt, ada, run["id"], _asks(WRITE, files=seen))
    waiting = await on_rrotor.run(ada, run["id"])
    assert waiting["status"] == "needs_input" and waiting["question"]["question"] == ASKS
    assert waiting["question"]["approval"] is True and waiting["question"]["options"] == ["yes", "no"]
    assert waiting["question"]["step"] == "file" and waiting["files"] == seen
    assert (await on_rrotor.answer(ada, run["id"], "yes"))["status"] == "dispatched"
    carried = on_rrotor.hub.last()
    assert isinstance(carried, Continue) and carried.answer.startswith("The person said yes to that.")
    # the yes is to that change alone, and is used up by it
    assert await _change(on_rrotor, run["id"], MOVE) == {"result": {"allowed": False}}
    other = {**WRITE, "path": "/Users/ana/Notes/Other.md"}
    assert await _change(on_rrotor, run["id"], other) == {"result": {"allowed": False}}
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": True}}
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": False}}
    # a move, asked and answered the same way; a no keeps nothing
    await on_rrotor.landed(rt, ada, run["id"], _asks(MOVE))
    await on_rrotor.answer(ada, run["id"], "yes")
    elsewhere = {**MOVE, "to": "/Users/ana/Notes/else.txt"}
    assert await _change(on_rrotor, run["id"], elsewhere) == {"result": {"allowed": False}}
    assert await _change(on_rrotor, run["id"], MOVE) == {"result": {"allowed": True}}
    await on_rrotor.landed(rt, ada, run["id"], _asks(WRITE))
    await on_rrotor.answer(ada, run["id"], "no")
    assert on_rrotor.hub.last().answer.startswith("The person said no to that.")
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": False}}


def test_a_yes_to_a_change_is_kept_as_the_yes_to_that_change() -> None:
    who = uuid.uuid4()
    kept = approvals.granted_file({"question": ASKS, "file": MOVE}, "yes", who)
    assert list(kept) == ["file_change"] and kept["file_change"]["by"] == str(who) and kept["file_change"]["at"]
    assert {k: kept["file_change"][k] for k in MOVE} == MOVE
    assert approvals.granted_file({"file": MOVE}, "yes", None)["file_change"]["by"] is None
    assert approvals.granted_file({"file": MOVE}, "no", who) == {}
    assert approvals.granted_file({"file": {"action": "delete"}}, "yes", who) == {}
    assert approvals.granted_file({}, "yes", who) == {}


# What is kept with the run


async def test_a_run_keeps_the_names_of_its_files_and_the_turn_shows_them(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, run = await _on(on_rrotor, engine)
    read = [{"name": "Invoices/March.pdf", "did": "read"}, {"name": "Invoices/April.pdf", "did": "read"}]
    junk = [{"name": "x", "did": "deleted"}, {"name": 7, "did": "read"}, "y", {"name": "z", "did": "read", "text": "!"}]
    await on_rrotor.landed(rt, ada, run["id"], _asks(WRITE, files=[*read, *junk]))
    await on_rrotor.landed(rt, ada, run["id"], EXPIRED)
    await on_rrotor.answer(ada, run["id"], "yes")
    fresh = on_rrotor.hub.last()  # the wait expired there: a fresh call, its folders and file tools with it again
    assert isinstance(fresh, Call) and fresh.inputs["resume"] is True and fresh.inputs["file_tools"] is True
    assert fresh.folders == [DOCS, NOTES, KEPT] and fresh.inputs["message"].startswith("The person said yes")
    assert await _change(on_rrotor, run["id"], WRITE) == {"result": {"allowed": True}}  # the yes went with it
    # what the rrotor names after is added to what the run had
    after = [{"name": "Invoices/March.pdf", "did": "read"}, {"name": "Notes/Summary.md", "did": "written"}]
    await on_rrotor.landed(rt, ada, run["id"], left(output="Summarised in **Summary.md**.", files=after))
    ended = await on_rrotor.run(ada, run["id"])
    assert ended["status"] == "done" and ended["question"] is None
    assert ended["files"] == [  # what it changed first
        {"name": "Notes/Summary.md", "did": "written"},
        {"name": "Invoices/April.pdf", "did": "read"},
        {"name": "z", "did": "read"},
        {"name": "Invoices/March.pdf", "did": "read"},
    ]
    assert ended["data"] == {} and ended["links"] == [] and ended["apps"] == []  # names only, and not as its data


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


def test_the_files_kept_and_shown() -> None:
    many = [{"name": f"f{n}", "did": "read"} for n in range(300)]
    assert files.named(None) is None and files.named({}) is None and files.named([]) == []
    assert len(files.named(many) or []) == 200 and len(files.merged(many, many[:5])) == 200
    assert files.merged("junk", many[:2]) == many[:2]
    run = SimpleNamespace(data={"_files": [*many[:20], {"name": "new.md", "did": "written"}]})
    shown = files.of(run)
    assert len(shown) == 12 and (shown[0].name, shown[0].did) == ("new.md", "written")
    assert files.of(SimpleNamespace(data=None)) == []
