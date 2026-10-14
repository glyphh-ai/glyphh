"""The link's session where a real socket can't put it in a test: a rrotor gone before its hello, and a ping that
finds the rrotor gone."""

import uuid

import pytest

from glyphh_server.ops.link import hello as hello_step
from glyphh_server.ops.link import session
from glyphh_server.ops.link.hub import Link
from glyphh_server.ops.link.presence import Runtime


class _HungUp:
    """A WebSocket whose rrotor hung up: its next message is the disconnect; sending to it fails."""

    async def receive(self) -> dict[str, object]:
        return {"type": "websocket.disconnect", "code": 1006}

    async def send_text(self, _: str) -> None:
        raise RuntimeError('Cannot call "send" once a close message has been sent.')


async def test_a_rrotor_gone_before_its_hello_is_let_go() -> None:
    runtime = Runtime(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "local", None)
    assert await hello_step.read_hello(_HungUp(), runtime) is None  # type: ignore[arg-type]


async def test_a_ping_that_finds_the_rrotor_gone_ends_the_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session, "PING_EVERY", 0.01)
    link = Link(_HungUp(), uuid.uuid4())  # type: ignore[arg-type]
    await session._heartbeat(link, session.Clock())
