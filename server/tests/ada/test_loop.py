"""The stream loop's own cases: the group made once, consumers long gone removed, a dead worker's message claimed, a
message past its deadline dropped, one that stopped too many workers refused, a crash answered E_INTERNAL; and the
API's side: no worker within the timeout is 504, Redis down is 503."""

import json
import time
from typing import Any

import httpx
import pytest
from redis import Redis
from redis.exceptions import ResponseError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import loop, protocol
from glyphh_ada.api import HostRouter
from glyphh_ada.errors import Refusal
from glyphh_ada.loop import Alive, Heartbeat, Loop
from glyphh_ada.protocol import GROUP, SYNC, Message
from glyphh_server.app import create_app
from tests.ada.conftest import ADA, HOST, an_org
from tests.conftest import UNREACHABLE_REDIS, _client


def _loop(redis: Redis, answer: Any, queue: str = SYNC, consumer: str = "me") -> Loop:
    def dispatch(msg: Message) -> tuple[Any, int | None]:
        if isinstance(answer, Exception):
            raise answer
        return answer, 1

    made = Loop(queue, redis, consumer, dispatch)
    made.ensure_group()
    return made


def _send(redis: Redis, deadline: float | None = None) -> Message:
    msg = Message("o", "m", "query", {"x": 1}, deadline=time.time() + 30 if deadline is None else deadline)
    redis.xadd("ada:sync", msg.fields())
    return msg


def _reply(redis: Redis, msg: Message) -> dict[str, Any]:
    return dict(json.loads(redis.lpop(protocol.reply_key(msg.id))))


def test_a_message_is_answered_and_acknowledged(streams: Redis) -> None:
    worker = _loop(streams, {"top": "good"})
    worker.ensure_group()  # made already: BUSYGROUP is fine
    msg = _send(streams)
    assert worker.one() and not worker.one()
    assert _reply(streams, msg) == {"ok": True, "data": {"top": "good"}, "version": 1}
    assert streams.xpending("ada:sync", GROUP)["pending"] == 0
    assert streams.ttl(protocol.reply_key(msg.id)) == -2  # read, gone


def test_refusals_crashes_deadlines_and_deleted_entries(streams: Redis) -> None:
    refused = _send(streams)
    _loop(streams, Refusal("E_X", "no", 409, why="because")).one()
    assert _reply(streams, refused)["error"] == {"code": "E_X", "message": "no", "status": 409, "why": "because"}
    crashed = _send(streams)
    _loop(streams, RuntimeError("boom")).one()
    assert _reply(streams, crashed)["error"]["code"] == "E_INTERNAL"
    late = _send(streams, deadline=time.time() - 1)
    _loop(streams, "never").one()
    assert streams.lpop(protocol.reply_key(late.id)) is None


def test_a_claimed_entry_already_deleted_is_acknowledged(streams: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    gone = streams.xadd("ada:sync", Message("o", "m", "query").fields())
    worker = _loop(streams, "never")
    monkeypatch.setattr(streams, "xautoclaim", lambda *_, **__: ["0-0", [(gone, None)], []])  # as Redis 6.2 answers
    assert worker.one() is True


def test_a_dead_workers_message_is_claimed_and_one_that_kills_is_refused(
    streams: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(protocol.CLAIM_IDLE, SYNC, 0)
    alive = _loop(streams, "answered", consumer="alive")
    msg = _send(streams)
    streams.xreadgroup(GROUP, "dead", {"ada:sync": ">"}, count=1)  # taken, never answered
    alive.one()
    assert _reply(streams, msg)["data"] == "answered"
    poison = _send(streams)
    taken = streams.xreadgroup(GROUP, "dead", {"ada:sync": ">"}, count=1)[0][1][0][0]
    for n in range(protocol.MAX_DELIVERIES):  # each claim a worker that took it and died
        streams.xclaim("ada:sync", GROUP, f"dead{n}", 0, [taken])
    _loop(streams, "never", consumer="alive").one()
    assert _reply(streams, poison)["error"]["code"] == "E_INTERNAL"


def test_long_gone_consumers_leave_and_other_errors_raise(streams: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    _loop(streams, "x")
    streams.xreadgroup(GROUP, "ghost", {"ada:sync": ">"}, count=1)
    monkeypatch.setattr(loop, "STALE_CONSUMER_MS", -1)
    _loop(streams, "x")
    assert "ghost" not in [c["name"] for c in streams.xinfo_consumers("ada:sync", GROUP)]
    streams.set("ada:jobs", "not a stream")
    with pytest.raises(ResponseError):
        _loop(streams, "x", queue="jobs")


def test_consumer_cleanup_does_nothing_where_redis_lists_no_consumers(
    streams: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    removed: list[str] = []
    monkeypatch.setattr(loop, "STALE_CONSUMER_MS", -1)
    monkeypatch.setattr(streams, "xgroup_delconsumer", lambda *a: removed.append(a[2]))
    monkeypatch.setattr(streams, "xinfo_consumers", lambda *_: [])  # Upstash
    _loop(streams, "x")
    monkeypatch.setattr(streams, "xinfo_consumers", lambda *_: [{"name": "odd"}])  # a reply without its numbers
    _loop(streams, "x")
    assert removed == []


def test_a_worker_says_it_is_alive_on_each_stream_and_leaves_when_it_stops(streams: Redis) -> None:
    keys = [protocol.alive_key("ada:sync"), protocol.alive_key("ada:sync:9.9.9")]
    assert keys == ["ada:alive:sync", "ada:alive:sync:9.9.9"]
    streams.delete(*keys)
    old = time.time() - protocol.ALIVE_FORGET - 1
    streams.zadd(keys[0], {"long-gone": old})
    worker = Loop(SYNC, streams, "me", lambda _: (None, None), ["ada:sync", "ada:sync:9.9.9"])
    with worker.alive() as beating:
        time.sleep(0.1)
        assert [streams.zrange(k, 0, -1) for k in keys] == [["me"], ["me"]]  # the long gone dropped
        assert 0 < streams.ttl(keys[0]) <= protocol.ALIVE_FORGET
        assert beating.beat(now=time.time() + 5)
        assert streams.zscore(keys[1], "me") > time.time()
    assert [streams.exists(k) for k in keys] == [0, 0]
    with Alive(streams, ["ada:jobs"], "quick", every=0.01):
        time.sleep(0.1)  # beats again and again
    down = Redis.from_url(UNREACHABLE_REDIS, socket_connect_timeout=0.2)
    with Alive(down, ["ada:sync"], "me") as lost:  # Redis down: tried again at the next beat, never raised
        assert lost.beat() is False


def test_a_heartbeat_keeps_a_message_from_going_idle(streams: Redis) -> None:
    _loop(streams, "x")
    _send(streams)
    taken = streams.xreadgroup(GROUP, "me", {"ada:sync": ">"}, count=1)[0][1][0][0]
    time.sleep(0.2)
    with Heartbeat(streams, "ada:sync", "me", taken, 0.05):
        time.sleep(0.2)
    idle = streams.xpending_range("ada:sync", GROUP, "-", "+", 1)[0]["time_since_delivered"]
    assert idle < 150


async def test_no_worker_is_504_and_no_redis_is_503(
    engine: AsyncEngine, ada: httpx.AsyncClient, streams: Redis
) -> None:
    _, key = await an_org(engine, ada)
    slow = create_app(ADA.model_copy(update={"ada_read_timeout": 0.2}))
    async for c in _client(slow):
        timed = await c.get(f"http://{HOST}/v1/models", headers=key)
        assert (timed.status_code, timed.json()["error"]["code"]) == (504, "E_TIMEOUT")
    async for c in _client(create_app(ADA.model_copy(update={"redis_url": UNREACHABLE_REDIS}))):
        down = await c.get(f"http://{HOST}/v1/models", headers=key)
        assert (down.status_code, down.json()["error"]["code"]) == (503, "E_UNAVAILABLE")


async def test_the_host_router_passes_the_rest_on() -> None:
    seen: list[str] = []

    async def server(scope: Any, receive: Any, send: Any) -> None:
        seen.append("server")

    async def ada(scope: Any, receive: Any, send: Any) -> None:
        seen.append("ada")

    router = HostRouter(server, ada, {"ada.test"})
    await router({"type": "lifespan"}, None, None)
    await router({"type": "http", "headers": []}, None, None)
    await router({"type": "http", "headers": [(b"x", b"y"), (b"host", b"ada.test:443")]}, None, None)
    assert seen == ["server", "server", "ada"]
