"""A worker killed mid-request loses nothing: another claims its message once it stops heartbeating, answers it, and
what the dead one had not committed is rolled back with its connection; a write answered once is never made twice."""

import asyncio
import os
import signal
from multiprocessing.process import BaseProcess

import httpx
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.handlers import handle
from glyphh_ada.process import Worker
from glyphh_ada.protocol import GROUP, Message
from tests.ada.conftest import a_model, an_org, cases
from tests.ada.conftest import start_process as _start


async def _pending(redis: Redis, at_least: int = 1) -> list[dict]:
    for _ in range(3000):
        found = redis.xpending_range("ada:sync", GROUP, min="-", max="+", count=10)
        if len(found) >= at_least:
            return list(found)
        await asyncio.sleep(0.005)
    raise AssertionError("no worker took the message")


async def test_a_worker_killed_mid_request_loses_nothing(
    engine: AsyncEngine, ada: httpx.AsyncClient, streams: Redis, spawn: list[BaseProcess]
) -> None:
    _, key = await an_org(engine, ada)
    first = _start(spawn)
    await a_model(ada, key)
    load = asyncio.create_task(ada.post("/v1/models/shapes/record_many", json={"cases": cases(1000)}, headers=key))
    taken = await _pending(streams)
    os.kill(first.pid, signal.SIGSTOP)  # mid-request: its heartbeat stops with it
    assert not load.done()
    second = _start(spawn)
    for _ in range(2000):  # the second claims it once it has sat idle CLAIM_IDLE
        now = streams.xpending_range("ada:sync", GROUP, min="-", max="+", count=10)
        if now and now[0]["consumer"] != taken[0]["consumer"]:
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("no other worker claimed the message")
    os.kill(first.pid, signal.SIGKILL)  # its connection drops, its transaction with it
    answered = await load
    assert answered.status_code == 200 and answered.json()["added"] == 1000, answered.text
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 1000
    assert second.is_alive() and streams.xpending_range("ada:sync", GROUP, min="-", max="+", count=10) == []


async def test_a_write_taken_again_is_answered_and_not_made_twice(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key)
    msg = Message(str(who.org_id), "shapes", "record_many", {"cases": cases(7)}, author="t")
    first = await asyncio.to_thread(handle, worker.ctx, msg)
    again = await asyncio.to_thread(handle, worker.ctx, msg)  # as a worker that claimed it after the first died
    assert first == again and first[0]["added"] == 7
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 7
