"""The real thing, end to end: the server's own run path with the real Claude Agent SDK against the live Anthropic
API (docs/specs/bot-agent-loop.md). Pipedream and Ada are the tests' fakes; the agent, its session, its tools' wiring,
the permission callback, the session store in Postgres and the metering are real. It runs only when LIVE_ANTHROPIC_KEY
is set (never in CI): `LIVE_ANTHROPIC_KEY=... pytest tests/bots/test_live.py -o addopts="" -s`."""

import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots.agent import sdk
from glyphh_server.ops.bots.agent.turn import Ended, Turn
from tests.bots.conftest import BOTS, Served, answered, connected, made_bot, ran, serve
from tests.bots.fakes import FakePipedream
from tests.db.helpers import Person

KEY: str = os.environ.get("LIVE_ANTHROPIC_KEY", "")
MODEL: str = os.environ.get("LIVE_MODEL", "claude-haiku-5-5")
GATE: str = "bot-inbox-cat-gate-worth"
pytestmark = pytest.mark.skipif(not KEY, reason="LIVE_ANTHROPIC_KEY is not set: no live check")


class Watched:
    """The real turn, with what each go left kept for the test to read."""

    def __init__(self) -> None:
        self.goes: list[tuple[Turn, Ended]] = []

    async def __call__(self, turn: Turn) -> Ended:
        got = await sdk.run(turn)
        self.goes.append((turn, got))
        return got


@pytest.fixture
async def live(engine: AsyncEngine) -> AsyncIterator[tuple[Served, Watched]]:
    async for s in serve(BOTS.model_copy(update={"anthropic_api_key": KEY}), FakePipedream()):
        watched = Watched()
        s.app.state.bots.agent = watched
        yield s, watched


def said(run: dict[str, Any]) -> str:
    return f"{run['status']} in={run['input_tokens']} out={run['output_tokens']} cost_micros={run['cost_micros']}"


async def test_hello_then_a_real_task(live: tuple[Served, Watched], ana: Person) -> None:
    s, watched = live
    gmail = await connected(s, ana, allow=False)  # nothing set on the connection: reading runs, sending asks
    scope = [{"connection_id": gmail["id"], "tools": ["gmail-find-email", "gmail-send-email"]}]
    bot = await made_bot(s, ana, model=MODEL, effort="low", permission_mode="ask", connections=scope)
    s.ada.cases[GATE].append(({}, "skip"))
    s.ada.rule[GATE] = lambda case: ("skip", 0.95) if "won" in case["m"]["s"]["subject"] else ("answer", 0.4)

    hello = await ran(s, ana, bot["slug"], "Hi there")
    print("\nHI THERE ->", said(hello), "\n", hello["output"])
    assert hello["status"] == "done" and hello["output"].strip()
    assert hello["steps"] == [] and s.pd.runs == [], "a greeting used a tool"
    listed = watched.goes[0][1].tools
    print("the session's tools:", listed)
    assert listed and all(t.startswith("mcp__bot__") or t == "Skill" for t in listed), listed
    assert hello["input_tokens"] > 0 and hello["output_tokens"] > 0

    task = "Find my unread mail, decide which is worth answering, and send a short reply to grace@navy.test for each."
    run = await ran(s, ana, bot["slug"], task)
    asked: list[str] = []
    for _ in range(6):
        if run["status"] != "needs_input":
            break
        q = run["question"]
        asked.append("approval" if q["approval"] else "decision")
        print("ASKED ->", q["question"], "|", q.get("detail") or [b["label"] for b in q["batch"]])
        run = await answered(s, ana, run["id"], "yes" if q["approval"] else "rest=answer")
    print("TASK ->", said(run), "\n", run["output"], "\nsteps:", [(x["title"], x["ok"]) for x in run["steps"]])
    print(
        "asked:", asked, "| goes:", len(watched.goes), "| sessions resumed:", [bool(t.session) for t, _ in watched.goes]
    )
    assert run["status"] == "done" and run["output"].strip(), run
    assert "decision" in asked and "approval" in asked, asked
    used = [r["id"] for r in s.pd.runs]
    assert "gmail-find-email" in used and used.count("gmail-send-email") >= 1, used
    assert s.ada.outcomes(GATE)[-1] == "answer"  # the person's answer was learned
    assert run["input_tokens"] > 0 and run["output_tokens"] > 0
    res = await s.http.get(f"/v1/bots/{bot['slug']}/decisions", headers=ana.headers)
    print("decisions:", [(d["label"], d["now"], d["who"]) for d in res.json()["decisions"]])
    assert {d["who"] for d in res.json()["decisions"]} == {"ada", "you"}
