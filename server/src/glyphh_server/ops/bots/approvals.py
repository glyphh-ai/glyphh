"""The person's yes to a step of a bot's run on a rrotor, kept on the server (docs/specs/bots.md, 9): the rrotor
holds the run, so its own guard (the approvals cloud.guarded adds) is not trusted alone. Answering a run that waits
at an approval, the person's yes is kept by the tool that step runs (the run's approvals: that one alone, replacing
any before; any other answer leaves none). A tool call from the rrotor of a tool to ask about then runs only by
taking that yes: one call, of that tool, for that run; without one it is refused, and logged."""

import logging
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.ops.bots import runs

log = logging.getLogger("glyphh.bots")
UNAPPROVED: str = "{tool} asks the person first, and this run has no yes of theirs to it: answer its approval."


def _tool(spec: dict[str, Any], step: Any) -> str | None:
    found = next((s for s in spec.get("loop") or [] if isinstance(s, dict) and s.get("id") == step), None)
    run = found.get("run") if found else None
    return run if isinstance(run, str) and run != "fetch" else None


def granted(question: dict[str, Any], spec: dict[str, Any], answer: Any, by: uuid.UUID | None) -> dict[str, Any]:
    """The run's approvals once the person answers `question` with `answer`: the yes to its step, by the tool it runs;
    none for a no, or for a question that is not an approval of a step that runs a tool."""
    tool = _tool(spec, question.get("step")) if question.get("approval") else None
    if tool is None or answer != "yes":
        return {}
    return {tool: {"step": question["step"], "by": str(by) if by else None, "at": runs.now().isoformat()}}


TAKE = text(
    "UPDATE bot_runs SET approvals = approvals - :tool WHERE id = :run AND approvals ? :tool RETURNING approvals"
)


async def take(conn: AsyncConnection, run_id: uuid.UUID, tool: str) -> bool:
    """The yes to `tool` on the run, used up (one call each); False when the run has none."""
    took = (await conn.execute(TAKE, {"run": run_id, "tool": tool})).first() is not None
    if not took:
        log.warning("bot tool refused: no approval", extra={"run_id": str(run_id), "tool": tool})
    return took
