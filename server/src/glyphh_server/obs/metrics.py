"""The server's own request metrics, for its staff (admin/infra.py): every request's time in a histogram, and every
request counted by route and status class (2xx, 4xx, 5xx). Counted in the process as each request ends (a few dict
additions, no I/O), and added to Redis every FLUSH_EVERY seconds in one pipeline: per minute, kept 7 days, and per
hour, kept 8.

Keys: `ops:lat:api:m:<YYYYMMDDHHMM>` and `…:h:<YYYYMMDDHH>`, a hash of bucket index → count with `n` (requests)
and `ms` (their total time); `ops:http:m:<minute>` and `ops:http:h:<hour>`, a hash of `<METHOD> <route>|<class>` →
count.
A bucket i holds times up to BOUNDS_MS[i]; the last, those past BOUNDS_MS[-1]."""

import asyncio
import contextlib
import logging
import time
from bisect import bisect_left
from collections import Counter, defaultdict

from redis.asyncio import Redis
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("glyphh.metrics")

BOUNDS_MS: tuple[int, ...] = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
KIND: str = "api"  # the one kind of request left: Ada's reads were counted apart, as `read`
MINUTE_TTL: int = 7 * 86_400 + 3_600
HOUR_TTL: int = 8 * 86_400
FLUSH_EVERY: float = 5.0


def minute_of(at: float) -> str:
    return time.strftime("%Y%m%d%H%M", time.gmtime(at))


class Recorder:
    """What this process counted since its last flush."""

    def __init__(self) -> None:
        self.latency: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        self.http: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def observe(self, method: str, route: str, status: int, ms: float, at: float | None = None) -> None:
        minute = minute_of(time.time() if at is None else at)
        counts = self.latency[(KIND, minute)]
        counts[str(bisect_left(BOUNDS_MS, ms))] += 1
        counts["n"] += 1
        counts["ms"] += round(ms)
        self.http[minute][f"{method} {route}|{status // 100}xx"] += 1

    async def flush(self, redis: Redis) -> int:
        """Everything counted, added to Redis; answers how many hashes it touched."""
        latency, http = self.latency, self.http
        self.latency, self.http = defaultdict(Counter), defaultdict(Counter)
        hashes: list[tuple[str, Counter[str]]] = []
        for (kind, minute), counts in latency.items():
            hashes += [(f"ops:lat:{kind}:m:{minute}", counts), (f"ops:lat:{kind}:h:{minute[:10]}", counts)]
        for minute, counts in http.items():
            hashes += [(f"ops:http:m:{minute}", counts), (f"ops:http:h:{minute[:10]}", counts)]
        if not hashes:
            return 0
        pipe = redis.pipeline(transaction=False)
        for key, counts in hashes:
            for name, n in counts.items():
                pipe.hincrby(key, name, n)
            pipe.expire(key, MINUTE_TTL if ":m:" in key else HOUR_TTL)
        await pipe.execute()
        return len(hashes)


async def flush_forever(recorder: Recorder, redis: Redis, every: float = FLUSH_EVERY) -> None:
    while True:
        await asyncio.sleep(every)
        try:
            await recorder.flush(redis)
        except Exception:  # noqa: BLE001  # those counts are lost; the next flush goes on
            log.info("metrics not flushed")


async def stop(task: asyncio.Task[None], recorder: Recorder, redis: Redis) -> None:
    """The flush loop stopped, and what it had not sent yet sent (best effort, at shutdown)."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    with contextlib.suppress(Exception):
        await recorder.flush(redis)


class MetricsMiddleware:
    """Each HTTP request's route (its template, `/v1/admin/orgs/{org_id}`; `unmatched` when none), status and time."""

    def __init__(self, app: ASGIApp, recorder: Recorder) -> None:
        self.app, self.recorder = app, recorder

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = {"status": 500}

        async def sending(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
            await send(message)

        began = time.perf_counter()
        try:
            await self.app(scope, receive, sending)
        finally:
            ms = (time.perf_counter() - began) * 1000
            self.recorder.observe(scope["method"], route_of(scope), state["status"], ms)


def route_of(scope: Scope) -> str:
    """The route's whole template, prefixes and all (FastAPI keeps an included router's routes under it, so the matched
    route alone has only its own part); `unmatched` when no route matched."""
    matched = (scope.get("fastapi") or {}).get("effective_route_context")
    return getattr(matched, "path", None) or getattr(scope.get("route"), "path", None) or "unmatched"
