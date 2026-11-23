"""The Agent SDK's turn, faked at the bots service's boundary (`Bots.agent`): a test scripts what the agent does each
go, as the calls it makes of its tools and the words it ends on. Each call goes to the run's desk exactly as the real
permission callback sends it (ops/bots/agent/sdk.py), so permissions, Ada and the tools themselves are the server's
own; a call the desk stops to ask the person about ends the go there, as the real turn's interrupt does."""

from collections.abc import Awaitable, Callable
from typing import Any

from glyphh_server.ops.bots.agent.turn import ASKED, Ended, Outcome, Turn

Go = Callable[[Turn], Awaitable[Ended]]
SESSION: str = "11111111-2222-3333-4444-555555555555"


def play(*calls: tuple[str, dict[str, Any]], text: str = "Done.", tokens: tuple[int, int] = (1000, 200)) -> Go:
    """A go that makes `calls` in turn, then says `text`; stopped by the first call that asks the person."""

    async def go(turn: Turn) -> Ended:
        for name, given in calls:
            got: Outcome = await turn.call(name, given)
            go.heard.append(got)  # type: ignore[attr-defined]
            if got.kind == ASKED:
                return Ended(session=SESSION, input_tokens=tokens[0], output_tokens=tokens[1], asked=True)
        return Ended(text=text, session=SESSION, input_tokens=tokens[0], output_tokens=tokens[1])

    go.heard = []  # type: ignore[attr-defined]
    return go


def fails(error: str) -> Go:
    async def go(turn: Turn) -> Ended:
        return Ended(session=SESSION, input_tokens=10, output_tokens=0, error=error)

    return go


class FakeAgent:
    """`script`: the goes to play, in turn; with none left, the agent says hello and uses no tool. `turns`: every
    turn it was handed."""

    def __init__(self) -> None:
        self.script: list[Go] = []
        self.turns: list[Turn] = []

    async def __call__(self, turn: Turn) -> Ended:
        self.turns.append(turn)
        go = self.script.pop(0) if self.script else play(text="Hello! I answer the mail worth answering.")
        return await go(turn)
