"""Claude, called as `claude -p` (`Claude`) or over the Claude API with the person's own Anthropic API key
(`ApiClaude`). A bot's agent step runs lean: only what the program gives it, no tools, no MCP servers, no settings,
hooks or CLAUDE.md, no session kept (a step costs cents, not a full session's context). The orchestrator's builder
alone gets Read and Write, in the new bot's folder only (`claude -p` only)."""

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

#: The Claude models an agent step may name (agent.md's `model`, or ApiClaude's own), a short name read as its id.
MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
#: Anthropic's prices, US dollars per million tokens (input, output), for the spend limits' count.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.1, 0.5)}
DEFAULT_MODEL = "claude-opus-5-5"
#: How hard Claude works on a step: the Claude API's `output_config.effort`, lowest to highest.
EFFORTS = ("low", "medium", "high", "xhigh", "max")
#: The models that take an effort, and the levels each takes. A model not here is asked without one.
EFFORT_MODELS = {"claude-opus-5-5": EFFORTS, "claude-sonnet-5-5": EFFORTS, "claude-haiku-5-5": EFFORTS}


def effort_for(model: str, effort: Optional[str]) -> Optional[str]:
    """The effort a request to this model carries: `effort` when the model takes it, else None (left out)."""
    return effort if effort in EFFORT_MODELS.get(model, ()) else None


@dataclass
class Answer:
    """What an agent step said, what it cost in US dollars, and its tokens."""

    text: str
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


def priced(model: str, input_tokens: int, output_tokens: int) -> float:
    """What these tokens cost on this model, in US dollars (an unknown model at Opus's price)."""
    i, o = PRICES.get(model, PRICES[DEFAULT_MODEL])
    return (input_tokens * i + output_tokens * o) / 1_000_000


class ApiClaude:
    """Agent steps over the Claude API, on the person's own Anthropic API key (`api_key`, else ANTHROPIC_API_KEY):
    they pay Anthropic for the tokens themselves. `model` is the default (agent.md's `model` wins); `client` is an
    `anthropic.Anthropic` (a fake in tests). `effort` (one of EFFORTS) is how hard Claude works on each step: sent
    as the API's `output_config.effort` when the step's model takes it, left out otherwise (None, the default: the
    model's own). Needs the `anthropic` package (`pip install glyphh[api]`)."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL, client: Any = None,
                 max_tokens: int = 16000, effort: Optional[str] = None) -> None:
        self.model = MODELS.get(model, model)
        self.max_tokens = max_tokens
        self.effort = effort
        if client is None:
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise BotError("no Anthropic API key: set ANTHROPIC_API_KEY, the bot's agent runs on your own key")
            try:
                import anthropic
            except ImportError:
                raise BotError("the anthropic package is not installed: pip install 'glyphh[api]'") from None
            client = anthropic.Anthropic(api_key=key, max_retries=3)
        self.client = client

    def agent(self, name: str, definition: Mapping[str, Any], prompt: str, *, turns: int = 3, seconds: int = 300) -> str:
        return self.answer(name, definition, prompt, turns=turns, seconds=seconds).text

    def answer(
        self, name: str, definition: Mapping[str, Any], prompt: str, *, turns: int = 3, seconds: int = 300
    ) -> Answer:
        """One agent step: the agent's prompt as the system prompt, the step's prompt as the one message (no tools,
        so one turn is all there is)."""
        model = MODELS.get(str(definition.get("model") or ""), str(definition.get("model") or "")) or self.model
        effort = effort_for(model, self.effort)
        more: Dict[str, Any] = {"output_config": {"effort": effort}} if effort else {}
        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=self.max_tokens,
                system=str(definition.get("prompt") or ""),
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "adaptive"},
                timeout=float(seconds),
                **more,
            ) as stream:
                message = stream.get_final_message()
        except Exception as e:  # noqa: BLE001  the API's errors (key, rate, overload) fail the step, said plainly
            raise BotError(f"Claude failed: {type(e).__name__}: {str(e)[:300]}") from e
        if message.stop_reason == "refusal":
            raise BotError("Claude declined this step")
        text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text").strip()
        used_in, used_out = int(message.usage.input_tokens or 0), int(message.usage.output_tokens or 0)
        return Answer(text, priced(str(message.model or model), used_in, used_out), used_in, used_out)

    def build(self, prompt: str, folder: Path, *, turns: int = 20, seconds: int = 900) -> str:
        raise BotError("making a bot needs Claude Code (`claude -p`): ApiClaude runs agent steps only")


def from_env() -> "Claude | ApiClaude":
    """The Claude a bot command uses: the Claude API on ANTHROPIC_API_KEY when GLYPHH_BOT_CLAUDE is `api` (rrotor
    sets it; GLYPHH_BOT_MODEL its model, GLYPHH_BOT_EFFORT its effort), else `claude -p`."""
    if os.environ.get("GLYPHH_BOT_CLAUDE") == "api":
        effort = os.environ.get("GLYPHH_BOT_EFFORT") or None
        return ApiClaude(model=os.environ.get("GLYPHH_BOT_MODEL") or DEFAULT_MODEL, effort=effort)
    return Claude()


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
        usage = got.get("usage") if isinstance(got.get("usage"), dict) else {}
        tokens = [int(usage.get(k) or 0) if isinstance(usage.get(k), int) else 0 for k in ("input_tokens", "output_tokens")]
        return Answer(str(got.get("result") or "").strip(), max(0.0, cost), *tokens)

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
