"""A burst of decides, as a live demo makes them: 50 at once on one model, answered by two worker processes (as one
shared-cpu-2x machine of the `ada` group runs), every one well inside the API's read timeout. Two models: one small
enough to be read whole (under the kernel's EXACT_BELOW) and one the store shortlists."""

import asyncio
import os
import time
from multiprocessing.process import BaseProcess
from typing import Any

import httpx
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.ada.conftest import SHAPES, a_model, an_org, cases, shape
from tests.ada.conftest import start_process as _start

BURST: int = 50
WORKERS: int = 2
SPEC: dict[str, Any] = {**SHAPES, "dimension": 4096}  # the kernel's default dimension (glyphh_kernel.DIM)
# Under the read timeout with room to spare, on CI's runners and a laptop's Docker alike.
WORST: float = float(os.environ.get("GLYPHH_BURST_WORST", "5.0"))


async def _burst(ada: httpx.AsyncClient, key: dict[str, str], name: str) -> list[float]:
    async def one(i: int) -> float:
        start = time.monotonic()
        res = await ada.post(f"/v1/models/{name}/decide", json={"data": shape(10_000 + i, "r", 2)}, headers=key)
        assert res.status_code == 200, res.text
        return time.monotonic() - start

    return sorted(await asyncio.gather(*(one(i) for i in range(BURST))))


async def _ready(ada: httpx.AsyncClient, key: dict[str, str], name: str) -> None:
    """Each worker has answered once (its process started, its connection made)."""
    for _ in range(WORKERS * 2):
        assert (await ada.post(f"/v1/models/{name}/decide", json={"data": shape(1)}, headers=key)).status_code == 200


async def test_a_burst_of_decides_is_answered_well_inside_the_timeout(
    engine: AsyncEngine, ada: httpx.AsyncClient, streams: Redis, spawn: list[BaseProcess]
) -> None:
    _, key = await an_org(engine, ada)
    for _ in range(WORKERS):
        _start(spawn)
    await a_model(ada, key, "small", 300, SPEC)
    await a_model(ada, key, "large", 0, SPEC)
    for start in range(0, 3000, 1000):
        done = await ada.post("/v1/models/large/record_many", json={"cases": cases(1000, start)}, headers=key)
        assert done.status_code == 200, done.text
    for name in ("small", "large"):
        await _ready(ada, key, name)
        took = await _burst(ada, key, name)
        print(f"\n{name}: median {took[len(took) // 2]:.2f} s, slowest {took[-1]:.2f} s for {BURST} at once")
        assert took[-1] < WORST, f"{name}: the slowest of {BURST} took {took[-1]:.2f} s"
