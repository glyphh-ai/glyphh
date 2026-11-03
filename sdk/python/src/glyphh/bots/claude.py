"""Claude, called as `claude -p`. A bot's agent step runs lean: only what the program gives it, no tools, no MCP
servers, no settings, hooks or CLAUDE.md, no session kept (a step costs cents, not a full session's context). The
orchestrator's builder alone gets Read and Write, in the new bot's folder only."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from .package import BotError

Run = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass
class Answer:
    """What an agent step said, and what it cost in US dollars."""

    text: str
    cost_usd: float = 0.0


class Claude:
    """`claude -p`, for agent steps and the builder. `command` is GLYPHH_CLAUDE, else `claude` on the PATH; `run` is
    how it is started (subprocess.run; a fake in tests)."""

    def __init__(self, command: Optional[str] = None, run: Optional[Run] = None) -> None:
        self.command = command or os.environ.get("GLYPHH_CLAUDE") or "claude"
        self._run: Run = run or subprocess.run

    def _call(self, args: List[str], cwd: Path, seconds: int) -> Dict[str, Any]:
        try:
            out = self._run([self.command, *args], capture_output=True, text=True, cwd=str(cwd), timeout=seconds)
        except FileNotFoundError:
            raise BotError(f"{self.command} is not installed: bots call Claude Code's `claude -p`") from None
        except subprocess.TimeoutExpired:
            raise BotError(f"Claude did not answer within {seconds} s") from None
        if out.returncode:
            said = (out.stderr or "").strip()[:300] or (out.stdout or "").strip()[:300]
            raise BotError(f"Claude failed: {said or f'exit {out.returncode}'}")
        try:
            answer = json.loads(out.stdout)
        except ValueError:
            raise BotError(f"Claude's answer is not JSON: {(out.stdout or '')[:200]}") from None
        if not isinstance(answer, dict):
            raise BotError("Claude's answer is not a JSON object")
        if answer.get("is_error"):
            raise BotError(f"Claude failed: {str(answer.get('result') or answer.get('subtype') or '')[:300]}")
        return answer

    def agent(self, name: str, definition: Mapping[str, Any], prompt: str, *, turns: int = 3, seconds: int = 300) -> str:
        """One agent step: the bot's agent answers the prompt, with nothing else before it."""
        return self.answer(name, definition, prompt, turns=turns, seconds=seconds).text

    def answer(
        self, name: str, definition: Mapping[str, Any], prompt: str, *, turns: int = 3, seconds: int = 300
    ) -> "Answer":
        """One agent step, with what it cost (`total_cost_usd`, as `claude -p` reports it; 0 when it says none)."""
        args = [
            "-p",
            "--agents",
            json.dumps({name: dict(definition)}),
            "--agent",
            name,
            "--tools",
            "",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--max-turns",
            str(turns),
            prompt,
        ]
        got = self._call(args, Path(tempfile.gettempdir()), seconds)
        try:
            cost = float(got.get("total_cost_usd") or 0.0)
        except (TypeError, ValueError):
            cost = 0.0
        return Answer(str(got.get("result") or "").strip(), max(0.0, cost))

    def build(self, prompt: str, folder: Path, *, turns: int = 20, seconds: int = 900) -> str:
        """The builder: Claude writes a bot's files into `folder` (Read and Write only, edits there accepted)."""
        args = [
            "-p",
            "--tools",
            "Read,Write",
            "--permission-mode",
            "acceptEdits",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--max-turns",
            str(turns),
            prompt,
        ]
        return str(self._call(args, folder, seconds).get("result") or "").strip()
