"""The person's yes to a step of a bot's run on a rrotor, kept on the server (docs/specs/bots.md, 9): the rrotor
holds the run, so its own guard (the approvals cloud.guarded adds) is not trusted alone. Answering a run that waits
at an approval, the person's yes is kept by the tool that step runs (the run's approvals: that one alone, replacing
any before; any other answer leaves none). A tool call from the rrotor of a tool to ask about then runs only by
taking that yes: one call, of that tool, for that run; without one it is refused, and logged.

A change to a file of the bot's folders is held the same way (ops/bots/files.py): the question a run asks before a
write or a move names the change (`question.file`), the person's yes is kept as the yes to that change (its action
and paths), and the rrotor's `file_change` for the same change takes it, once."""

import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.ops.bots import files, runs

log = logging.getLogger("glyphh.bots")
UNAPPROVED: str = "{tool} asks the person first, and this run has no yes of theirs to it: answer its approval."


def _tool(spec: dict[str, Any], step: Any) -> str | None:
    found = next((s for s in spec.get("loop") or [] if isinstance(s, dict) and s.get("id") == step), None)
    run = found.get("run") if found else None
    return run if isinstance(run, str) and run != "fetch" else None


def granted(question: dict[str, Any], spec: dict[str, Any], answer: Any, by: uuid.UUID | None) -> dict[str, Any]:
    """The run's approvals once the person answers `question` with `answer`: the yes to its step, by the tool it runs;
    none for a no, or for a question that is not an approval of a step that runs a tool."""
    if not question.get("approval") or answer != "yes":
        return {}
    said = {"by": str(by) if by else None, "at": runs.now().isoformat()}
    asked = files.change(question.get("file"))
    if asked is not None:  # a change to a file of the bot's folders: the yes is to that change alone
        return {files.TOOL: {**asked, **said}}
    tool = _tool(spec, question.get("step"))
    return {tool: {"step": question["step"], **said}} if tool is not None else {}


TAKE = text(
    "UPDATE bot_runs SET approvals = approvals - :tool WHERE id = :run AND approvals ? :tool RETURNING approvals"
)


async def take(conn: AsyncConnection, run_id: uuid.UUID, tool: str) -> bool:
    """The yes to `tool` on the run, used up (one call each); False when the run has none."""
    took = (await conn.execute(TAKE, {"run": run_id, "tool": tool})).first() is not None
    if not took:
        log.warning("bot tool refused: no approval", extra={"run_id": str(run_id), "tool": tool})
    return took


TAKE_FILE = text(
    "UPDATE bot_runs SET approvals = approvals - 'file_change' WHERE id = :run "
    "AND approvals -> 'file_change' ->> 'action' = :action AND approvals -> 'file_change' ->> 'path' = :path "
    "AND coalesce(approvals -> 'file_change' ->> 'to', '') = :to RETURNING approvals"
)


async def take_file(conn: AsyncConnection, run_id: uuid.UUID, asked: dict[str, str]) -> bool:
    """The yes to this very change (its action and paths) on the run, used up; False when the run has none: the
    person is then asked (ops/bots/files.py)."""
    said = {"run": run_id, "action": asked["action"], "path": asked["path"], "to": asked.get("to", "")}
    return (await conn.execute(TAKE_FILE, said)).first() is not None
