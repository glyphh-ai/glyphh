"""One go of a bot's agent, as the server hands it to the Agent SDK and hears back (ops/bots/agent/sdk.py is the
real thing; a test gives the bots service a fake of the same shape, `Bots.agent`)."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import ResultMessage

from glyphh_server.ops.bots.agent.tools import Tool

RESULT, ERROR, ASKED = "result", "error", "ask"


@dataclass(frozen=True)
class Outcome:
    """What a tool's call came to: its result, an error the agent is told, or the run stopped to ask the person."""

    kind: str
    value: Any = None


Call = Callable[[str, dict[str, Any]], Awaitable[Outcome]]
Allowed = Callable[[str, dict[str, Any]], Awaitable[Outcome | None]]


@dataclass
class Turn:
    system: str
    message: str
    tools: list[Tool]
    call: Call  # a tool's call, by the name the agent used: allowed, then made
    allowed: Allowed  # whether the bot may make it: None, or the error it is told, or the approval the run waits on
    made: Call  # the call made (once allowed): the tool's result, an error, or the run stopped to ask
    model: str
    effort: str | None
    key: str  # the Anthropic API key it is billed on
    folder: Path  # the run's own folder: the same path each go, emptied before and removed after
    store: Any  # the run's session store (ops/bots/agent/session.py)
    session: str = ""  # the session to carry on; none: a new one
    turns: int = 25
    seconds: float = 300.0
    plugins: list[Path] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class Ended:
    """How the go ended: the agent's final words, or that it stopped to ask, or why it failed; its session and the
    tokens it used (cache reads and writes counted as input)."""

    text: str = ""
    session: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    asked: bool = False
    error: str = ""
    tools: list[str] = field(default_factory=list)  # every tool the session had, as the SDK's init listed them


Agent = Callable[[Turn], Awaitable[Ended]]
STOPPED: dict[str, str] = {
    "error_max_turns": "It took more steps than a run may: ask for less at once.",
    "error_max_budget_usd": "It reached the most a run may spend.",
}


def tokens(usage: dict[str, Any] | None) -> tuple[int, int]:
    """A result's tokens in and out: cache reads and writes are input."""
    u = usage or {}
    spent = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return spent, int(u.get("output_tokens") or 0)


def ended(result: ResultMessage, words: list[str], asked: bool, session: str) -> Ended:
    """How a go ended, from the SDK's result message and the agent's last words."""
    spent_in, spent_out = tokens(result.usage)
    out = Ended(session=result.session_id or session, input_tokens=spent_in, output_tokens=spent_out, asked=asked)
    if asked:
        return out
    if result.is_error or result.subtype != "success":
        why = STOPPED.get(result.subtype) or "; ".join(result.errors or []) or result.result or result.subtype
        out.error = str(why)
        return out
    out.text = (result.result or "\n\n".join(words)).strip()
    return out
