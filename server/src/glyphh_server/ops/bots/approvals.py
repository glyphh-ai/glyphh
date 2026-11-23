"""The person's yes to a change of a file of a bot's folders, kept on the server (docs/specs/bots.md, 14). The
rrotor is the machine, so this is the bot's manners held in one place, as its tools' are (a yes to a tool's call is
ops/bots/agent/permit.py's): the question a run asks before a write or a move names the change (`question.file`),
the person's yes is kept as the yes to that change (its action and paths), and the rrotor's `file_change` for the
same change takes it, once."""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.ops.bots import files, runs


def granted_file(question: dict[str, Any], answer: Any, by: uuid.UUID | None) -> dict[str, Any]:
    """The run's approvals once the person answers a question about a file's change: their yes to that change;
    none for a no."""
    asked = files.change(question.get("file"))
    if asked is None or answer != "yes":
        return {}
    return {files.TOOL: {**asked, "by": str(by) if by else None, "at": runs.now().isoformat()}}


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
