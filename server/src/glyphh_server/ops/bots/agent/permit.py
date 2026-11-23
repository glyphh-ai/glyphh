"""Permission before a bot acts (docs/specs/bot-agent-loop.md, 5): what the bot's "Before it acts" and the tool's
connection make of a call. A tool its connection denies is refused in every mode; a read-only tool never asks unless
its connection says to; an action asks under Ask me first unless its connection allows it, and under Follow each
app's settings unless its connection allows it; Act on its own asks nothing. The person's yes to a call is to that
very call (the tool and a digest of its input), used once."""

import hashlib
import json
from typing import Any

from glyphh_server.ops.bots.agent.tools import Tool

RUN, ASK, DENY = "run", "ask", "deny"
DENIED: str = "{title} is blocked on the {app} connection. Tell the person; they can allow it on that connection."
DETAIL_MAX: int = 600


def verdict(mode: str, tool: Tool) -> str:
    """run, ask or deny, for one of the bot's tools under its permission mode."""
    if tool.permission == DENY:
        return DENY
    if mode == "auto" or tool.permission == "allow":
        return RUN
    if tool.read_only:
        return ASK if tool.permission == ASK else RUN
    return ASK


def digest(given: dict[str, Any]) -> str:
    """A call's input, as the person's yes names it."""
    return hashlib.sha256(json.dumps(given, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _plain(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(_plain(v) for v in value)
    return json.dumps(value, default=str) if isinstance(value, dict) else str(value)


def detail(given: dict[str, Any]) -> str:
    """The call in plain words, for the person to say yes or no to: each thing it is given, a line."""
    lines = [f"{k.replace('_', ' ')}: {_plain(v)}" for k, v in given.items() if v not in (None, "", [], {})]
    said = "\n".join(lines)
    return said if len(said) <= DETAIL_MAX else said[: DETAIL_MAX - 1] + "…"


def question(tool: Tool, given: dict[str, Any]) -> dict[str, Any]:
    """The approval a run waits on before `tool` runs with `given`."""
    where = f" in {tool.app}" if tool.app else ""
    return {
        "question": f"{tool.title}{where}?",
        "options": ["yes", "no"],
        "approval": True,
        "step": tool.key,
        "tool": tool.key,
        "detail": detail(given),
        "digest": digest(given),
    }


def granted(question: dict[str, Any], answer: Any, by: Any, at: str) -> dict[str, Any]:
    """The run's approvals once the person answers: their yes to the call the question names; none for a no."""
    if not question.get("approval") or answer != "yes" or not question.get("tool"):
        return {}
    return {question["tool"]: {"digest": question.get("digest", ""), "by": str(by) if by else None, "at": at}}
