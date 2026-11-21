"""One go of the SDK's runner (glyphh.bots.Runner) for a bot, in a worker thread: its package opened in a folder of its
own with its state, the cloud's program (ops/bots/cloud.py), its Ada models reached with its own Ada key, its agent
steps on the org's own Anthropic key or Glyphh's (metered: let in by the hosted models' meter, then accounted). A go
starts a run, carries on a run that waited for the person, or corrects a gate; what it leaves (the runner's state,
the run's status, log, data, question and tokens) is the caller's to keep."""

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from glyphh.bots import BotError, Runner, RunResult

from glyphh_server.errors import GlyphhError
from glyphh_server.ops.bots import cloud, package

OUTPUT_MAX: int = 50_000
INSTALLED: str = "_glyphh_installed"


@dataclass
class Left:
    """What a go leaves: the runner's state, and for a run its outcome."""

    state: bytes | None
    result: RunResult | None = None
    answer: Any = None  # a correction's or a report's answer
    tokens: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    charged: int = 0  # microdollars, on Glyphh's key only


class Metered:
    """Agent steps on Glyphh's own key: each let in by the meter (the plan's allowance, then the org's balance) and its
    tokens charged after (`admit` and `record` are the meter's, run on the server's loop)."""

    def __init__(
        self, inner: Any, loop: asyncio.AbstractEventLoop, admit: Callable[[], Any], record: Callable[[Any, Any], Any]
    ) -> None:
        self.inner, self.loop, self.admit, self.record = inner, loop, admit, record
        self.charged = 0

    def _on_loop(self, ask: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(ask, self.loop).result(60)

    def answer(self, name: str, definition: Any, prompt: str, **kw: Any) -> Any:
        try:
            admitted = self._on_loop(self.admit())
        except GlyphhError as err:  # the allowance spent and no balance: the step fails, said as the meter says it
            raise BotError(err.message) from err
        got = self.inner.answer(name, definition, prompt, **kw)
        self.charged += int(self._on_loop(self.record(admitted, got)))
        return got


def output(bot: Any, result: RunResult) -> str:
    """The run's answer as text: the data of the last of its loop's steps that has any."""
    for step in reversed(bot.spec.get("loop") or []):
        value = result.data.get(step.get("id")) if isinstance(step, dict) else None
        if value is not None:
            text = value if isinstance(value, str) else json.dumps(value, default=str)
            return text[:OUTPUT_MAX]
    return ""


def installed(runner: Runner) -> None:
    """The bot's gate and memory models made and its seed lines kept, once for each shape of its gates and seed (the
    SDK's install keeps the seed lines again each time it is called)."""
    spec = runner.bot.spec
    shape = hashlib.sha256(json.dumps([spec.get("gates"), spec.get("seed")], sort_keys=True).encode()).hexdigest()
    if runner.store.state(INSTALLED) != shape:
        runner.install()
        runner.store.set_state(INSTALLED, shape)


def go(bot: Any, program: cloud.Program, ada: Any, claude: Any, act: Callable[[Runner], Any]) -> Left:
    """`act` on the bot's runner, its package and state opened for it; the state it leaves, kept."""
    with package.opened(bot, program) as pkg:
        runner = Runner(pkg, ada, claude=claude, fetch=cloud.fetch, notify=lambda title, text: None)
        installed(runner)
        got = act(runner)
        left = Left(package.state(pkg.dir), tokens=dict(runner.tokens), charged=getattr(claude, "charged", 0))
    if isinstance(got, RunResult):
        left.result = got
    else:
        left.answer = got
    return left
