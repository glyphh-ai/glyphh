"""Reading the request metrics back (obs/metrics.py): percentiles from the histograms, over the last minutes or hour by
hour, and requests by route with their 4xx and 5xx."""

import time
from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel
from redis.asyncio import Redis

from glyphh_server.obs.metrics import BOUNDS_MS, minute_of


class Percentiles(BaseModel):
    n: int
    p50: float | None
    p95: float | None
    p99: float | None
    mean: float | None


class Endpoint(BaseModel):
    method: str
    route: str
    total: int
    c4xx: int
    c5xx: int


def percentile(counts: Counter[str], q: float) -> float | None:
    """The q-th quantile in ms, interpolated in its bucket; the last bucket's bound past it; None with no requests."""
    n = counts.get("n", 0)
    if n == 0:
        return None
    target, seen = q * n, 0
    for i, upper in enumerate(BOUNDS_MS):
        here = counts.get(str(i), 0)
        if here and seen + here >= target:
            lower = BOUNDS_MS[i - 1] if i else 0
            return round(lower + (upper - lower) * (target - seen) / here, 1)
        seen += here
    return float(BOUNDS_MS[-1])


def summary(counts: Counter[str]) -> Percentiles:
    n = counts.get("n", 0)
    mean = round(counts.get("ms", 0) / n, 1) if n else None
    p = {f"p{q}": percentile(counts, q / 100) for q in (50, 95, 99)}
    return Percentiles(n=n, mean=mean, **p)


def minutes(count: int, now: float | None = None) -> list[str]:
    at = time.time() if now is None else now
    return [minute_of(at - 60 * i) for i in range(count)]


def hours(count: int, now: float | None = None) -> list[str]:
    at = time.time() if now is None else now
    return [minute_of(at - 3600 * i)[:10] for i in range(count)][::-1]


async def hashes(redis: Redis, keys: Iterable[str]) -> list[Counter[str]]:
    pipe = redis.pipeline(transaction=False)
    for key in keys:
        pipe.hgetall(key)
    return [Counter({k: int(v) for k, v in found.items()}) for found in await pipe.execute()]


def added(found: list[Counter[str]]) -> Counter[str]:
    total: Counter[str] = Counter()
    for c in found:
        total.update(c)
    return total


async def window(redis: Redis, kind: str, last_minutes: int, now: float | None = None) -> Percentiles:
    return summary(added(await hashes(redis, (f"ops:lat:{kind}:m:{m}" for m in minutes(last_minutes, now)))))


async def hourly(redis: Redis, kind: str, count: int, now: float | None = None) -> list[tuple[str, Percentiles]]:
    names = hours(count, now)
    return list(zip(names, map(summary, await hashes(redis, (f"ops:lat:{kind}:h:{h}" for h in names))), strict=True))


def endpoints(counts: Counter[str]) -> list[Endpoint]:
    """Requests by route, busiest first, from a `<METHOD> <route>|<class>` hash."""
    by: dict[tuple[str, str], Counter[str]] = {}
    for name, n in counts.items():
        call, _, klass = name.rpartition("|")
        method, _, route = call.partition(" ")
        by.setdefault((method, route), Counter())[klass] += n
    found = [
        Endpoint(method=m, route=r, total=c.total(), c4xx=c.get("4xx", 0), c5xx=c.get("5xx", 0))
        for (m, r), c in by.items()
    ]
    return sorted(found, key=lambda e: (-e.total, e.route, e.method))


async def http_window(redis: Redis, last_minutes: int, now: float | None = None) -> list[Endpoint]:
    return endpoints(added(await hashes(redis, (f"ops:http:m:{m}" for m in minutes(last_minutes, now)))))
