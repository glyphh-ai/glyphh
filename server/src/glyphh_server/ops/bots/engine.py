"""One go of the SDK's runner (glyphh.bots.Runner) on a bot's state, in a worker thread: its package opened in a
folder of its own with its state (the runner's store: its decisions, its runs, what its decisions' probes
measured), its Ada models reached with its own Ada key. A bot's run is the Agent SDK's (ops/bots/agent); the runner
is what keeps and trains what Ada decides for it (ops/bots/agent/ada.py, mend.py, training.py), unchanged since bots
were loops. What a go leaves (the state, and what `act` answered) is the caller's to keep."""

import asyncio
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from glyphh.bots import BotError, Runner

from glyphh_server.errors import GlyphhError
from glyphh_server.ops.bots import cloud, package, seeds

INSTALLED: str = "_glyphh_installed"


@dataclass
class Left:
    """What a go leaves: the runner's state, and what was asked of it."""

    state: bytes | None
    answer: Any = None


class Metered:
    """Claude requests on the bots' key, outside a run (the bot maker's): each let in by the meter (the plan's
    allowance, then the org's balance) and its tokens charged after (`admit` and `record` are the meter's, run on
    the server's loop)."""

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
        except GlyphhError as err:  # the allowance spent and no balance: said as the meter says it
            raise BotError(err.message) from err
        got = self.inner.answer(name, definition, prompt, **kw)
        self.charged += int(self._on_loop(self.record(admitted, got)))
        return got


def installed(runner: Runner) -> None:
    """The bot's decision and memory models made and its seed lines kept, once for each shape of its decisions and
    seed (the SDK's install keeps the seed lines again each time it is called); a decision made now gets its seed
    set's precedents (ops/bots/seeds.py)."""
    spec = runner.bot.spec
    shape = hashlib.sha256(json.dumps([spec.get("gates"), spec.get("seed")], sort_keys=True).encode()).hexdigest()
    if runner.store.state(INSTALLED) != shape:
        made = runner.install()["made"]
        seeds.plant(runner, made)
        runner.store.set_state(INSTALLED, shape)


def go(bot: Any, ada: Any, act: Callable[[Runner], Any]) -> Left:
    """`act` on the bot's runner, its package and state opened for it; the state it leaves, kept."""
    with package.opened(bot) as pkg:
        runner = Runner(pkg, ada, fetch=cloud.fetch, notify=lambda title, text: None)
        installed(runner)
        got = act(runner)
        return Left(package.state(pkg.dir), got)
