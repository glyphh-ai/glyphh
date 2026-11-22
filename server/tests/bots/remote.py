"""Bots and projects on the org's rrotors, under test: the server reached at an https address (a rrotor reaches it only
so), its link hub faked (what is sent to a rrotor kept, the rrotor linked or not), a rrotor of the org online, and
its results handed in as its link would hand them (app.state.bots.landed)."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import pytest
from glyphh.bots import RunResult
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.models import Rrotor
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import Message, Ran
from tests.bots.conftest import BOTS, Served, serve
from tests.bots.fakes import FakePipedream
from tests.db.helpers import Person
from tests.link import Rt, self_runtime

REMOTE: Settings = BOTS.model_copy(update={"public_url": "https://api.glyphh.test"})


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

    async def landed(self, rt: Rt, who: Person, run_id: uuid.UUID, result: dict[str, Any], seq: int = 0) -> int:
        """The rrotor's result for the call `run_id`, numbered past the last (or `seq`, a replay)."""
        if not seq:
            self.seq += 1
            seq = self.seq
        runtime = Runtime(rt.id, who.user_id, who.org_id, "self")
        await self.s.app.state.bots.landed(runtime, Ran(type="result", seq=seq, run_id=run_id, result=result))
        return seq


@pytest.fixture(name="on_rrotor")
async def rrotor_fixture(engine: AsyncEngine) -> AsyncIterator[OnRrotor]:
    async for s in serve(REMOTE, FakePipedream()):
        hub = FakeHub()
        s.app.state.bots.remote.hub = hub
        s.app.state.bots.projects.hub = hub
        yield OnRrotor(s, hub)


async def online(engine: AsyncEngine, who: Person, state: str = "online") -> Rt:
    """A rrotor of the person's org at an address of its own, linked now (or not)."""
    rt = await self_runtime(engine, who, f"https://rrotor-{uuid.uuid4().hex[:8]}.acme.test")
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(state=state))
    return rt


def result(status: str = "done", **over: Any) -> dict[str, Any]:
    """glyphh_bot's Result, as the SDK's RunResult.to_result makes it."""
    return RunResult(bot="inbox-cat", run_id="r1", status=status, **over).to_result()
