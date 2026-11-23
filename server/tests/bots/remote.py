"""Bots and projects on the org's rrotors, under test: the server reached at an https address (a rrotor reaches it only
so), its link hub faked (what is sent to a rrotor kept, the rrotor linked or not), a rrotor of the org online, and
its results handed in as its link would hand them (app.state.bots.landed).

A bot's run on a rrotor has no agent on the server (docs/specs/bot-agent-loop.md, 6.2): a test plays the rrotor. It
reads the `call` that went down the link (`OnRrotor.call`), calls the run's tools at its tool endpoint with the
call's token (`OnRrotor.tool`, as rrotor's agent_tools.Server does) and sends glyphh_bot's Result up the link
(`left`, as rrotor's agent_loop.left makes it; `OnRrotor.landed`)."""

import logging
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from glyphh.bots import RunResult
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.models import BotRun, Rrotor
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Call, Message, Ran
from tests.bots.conftest import BOTS, Served, made_bot, serve
from tests.bots.fakes import FakePipedream
from tests.db.helpers import Person, person
from tests.link import Rt, self_runtime

REMOTE: Settings = BOTS.model_copy(update={"public_url": "https://api.glyphh.test"})
VERSION: str = "0.9.0"  # the first rrotor whose glyphh_bot runs a bot as an agent
EXPIRED: dict[str, Any] = {"status": "expired", "step": "wait", "prompt": None, "data": {"reason": "No answer came."}}
GONE: dict[str, Any] = {  # a `continue` the rrotor had no run for (rrotord/link/handler.py)
    "status": "failed",
    "step": "continue",
    "prompt": None,
    "data": {"reason": "This rrotor has no such run.", "code": "E_RUN_MISSING"},
}


class FakeHub:
    """The link hub: each message sent to a rrotor kept; delivered while `up`."""

    def __init__(self) -> None:
        self.sent: list[tuple[uuid.UUID, Message]] = []
        self.up: bool = True

    async def deliver(self, runtime_id: uuid.UUID, message: Message) -> bool:
        self.sent.append((runtime_id, message))
        return self.up

    def last(self) -> Any:
        return self.sent[-1][1]


@dataclass
class OnRrotor:
    s: Served
    hub: FakeHub
    seq: int = 0

    async def landed(self, rt: Rt, who: Person, run_id: Any, result: dict[str, Any], seq: int = 0) -> int:
        """The rrotor's result for the call `run_id`, numbered past the last (or `seq`, a replay)."""
        if not seq:
            self.seq += 1
            seq = self.seq
        runtime = Runtime(rt.id, who.user_id, who.org_id, "self")
        msg = Ran(type="result", seq=seq, run_id=uuid.UUID(str(run_id)), result=result)
        await self.s.app.state.bots.landed(runtime, msg)
        return seq

    def call(self) -> Call:
        """The last call that went down the link."""
        return next(sent for _, sent in reversed(self.hub.sent) if isinstance(sent, Call))

    async def post(self, run_id: Any, token: str | None, tool: str, given: Any = None) -> tuple[int, Any]:
        """A tool called at the run's tool endpoint, as the rrotor calls it: the status and the body."""
        headers = {"authorization": f"Bearer {token}"} if token else {}
        body = {"tool": tool, "input": given}
        res = await self.s.http.post(f"/v1/bots/runs/{run_id}/tool", json=body, headers=headers)
        return res.status_code, res.json()

    async def tool(self, run_id: Any, tool: str, given: Any = None) -> Any:
        """The tool's answer to the run's last call's own token."""
        status, said = await self.post(run_id, self.call().inputs["tool_token"], tool, given)
        assert status == 200, said
        return said

    async def run(self, who: Person, run_id: Any) -> dict[str, Any]:
        res = await self.s.http.get(f"/v1/bot-runs/{run_id}", headers=who.headers)
        assert res.status_code == 200, res.text
        return dict(res.json())

    async def start(self, who: Person, slug: str = "inbox-cat", said: str = "lunch") -> dict[str, Any]:
        res = await self.s.http.post(f"/v1/bots/{slug}/runs", json={"input": said}, headers=who.headers)
        assert res.status_code == 202, res.text
        return dict(res.json())

    async def answer(self, who: Person, run_id: Any, answer: Any) -> dict[str, Any]:
        res = await self.s.http.post(f"/v1/bot-runs/{run_id}/answer", json={"answer": answer}, headers=who.headers)
        assert res.status_code == 202, res.text
        return dict(res.json())


@pytest.fixture(name="on_rrotor")
async def rrotor_fixture(engine: AsyncEngine) -> AsyncIterator[OnRrotor]:
    async for s in serve(REMOTE, FakePipedream()):
        hub = FakeHub()
        s.app.state.bots.remote.hub = hub
        s.app.state.bots.projects.hub = hub
        yield OnRrotor(s, hub)


async def online(engine: AsyncEngine, who: Person, state: str = "online", version: str | None = VERSION) -> Rt:
    """A rrotor of the person's org at an address of its own, linked now (or not), saying it runs `version`."""
    rt = await self_runtime(engine, who, f"https://rrotor-{uuid.uuid4().hex[:8]}.acme.test")
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(state=state, image_version=version))
    return rt


async def out(
    r: OnRrotor, engine: AsyncEngine, said: str = "lunch", plan: str = "Free", **over: Any
) -> tuple[Person, Rt, dict[str, Any]]:
    """A person (on `plan`: Enterprise has no rate limit), their rrotor and a run of their inbox bot (made with
    `over`) out on it."""
    who = await person(engine, plan)
    rt = await online(engine, who)
    bot = await made_bot(r.s, who, runs_on=str(rt.id), **over)
    return who, rt, await r.start(who, bot["slug"], said)


async def row(engine: AsyncEngine, run_id: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(select(BotRun).where(BotRun.id == uuid.UUID(str(run_id))))).one()


@contextmanager
def logged(name: str = "glyphh.bots") -> Iterator[list[logging.LogRecord]]:
    """What the bots (or the logger named) log meanwhile (whether or not pytest's own log capture is on)."""
    said: list[logging.LogRecord] = []

    class Kept(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            said.append(record)

    log, kept = logging.getLogger(name), Kept(logging.INFO)
    level = log.level
    log.addHandler(kept)
    log.setLevel(logging.INFO)
    try:
        yield said
    finally:
        log.removeHandler(kept)
        log.setLevel(level)


def left(status: str = "done", prompt: str | None = None, tokens: Any = (0, 0), **data: Any) -> Any:
    """glyphh_bot's Result of an agent's go, as rrotor's agent_loop.left makes it: the run's tokens so far."""
    spent = {"input_tokens": tokens[0], "output_tokens": tokens[1]} if isinstance(tokens, tuple) else tokens
    said = {"output": "", "steps": [], "files": [], "tokens": spent, **data}
    return {"status": status, "step": None if status == "done" else "agent", "prompt": prompt, "data": said}


def result(status: str = "done", **over: Any) -> dict[str, Any]:
    """A Result as the SDK's RunResult.to_result makes it (a project's steps still answer so)."""
    return RunResult(bot="inbox-cat", run_id="r1", status=status, **over).to_result()
