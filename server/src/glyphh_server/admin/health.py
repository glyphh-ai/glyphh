"""The staff view's infrastructure page: Ada's queues and workers, read and API latency (the last 5 minutes, the last
hour and hour by hour), requests by route with their errors, Ada's jobs of the last week (admin/adascan.py), Postgres,
Redis, the tick, and the alerts they raise (admin/alerts.py)."""

from datetime import timedelta
from statistics import quantiles

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.admin import adascan, infra
from glyphh_server.admin.alerts import THRESHOLDS, Alert, alerts
from glyphh_server.obs import events_store, latency
from glyphh_server.obs.latency import Endpoint, Percentiles

HOURS: int = 24
ROUTES: int = 30


class Hour(BaseModel):
    hour: str
    latency: Percentiles


class Latency(BaseModel):
    last_5m: Percentiles
    last_hour: Percentiles
    hourly: list[Hour]


class HttpHour(BaseModel):
    hour: str
    total: int
    c5xx: int


class Http(BaseModel):
    total: int
    c5xx: int
    routes: list[Endpoint]
    hourly: list[HttpHour]


class JobStat(BaseModel):
    kind: str
    total: int
    failed: int
    unfinished: int
    p50_seconds: float | None
    p95_seconds: float | None


class Infra(BaseModel):
    ada_cloud: bool
    alerts: list[Alert]
    thresholds: dict[str, float]
    queues: list[infra.Queue]
    tick: infra.Tick
    read: Latency
    api: Latency
    http: Http
    jobs: list[JobStat]
    database: infra.Database
    redis: infra.RedisMemory


async def _latency(redis: Redis, kind: str) -> Latency:
    hourly = [Hour(hour=h, latency=p) for h, p in await latency.hourly(redis, kind, HOURS)]
    return Latency(
        last_5m=await latency.window(redis, kind, 5), last_hour=await latency.window(redis, kind, 60), hourly=hourly
    )


async def _http(redis: Redis) -> Http:
    routes = await latency.http_window(redis, 60)
    names = latency.hours(HOURS)
    found = await latency.hashes(redis, (f"ops:http:h:{h}" for h in names))
    hourly = [
        HttpHour(hour=h, total=c.total(), c5xx=sum(n for k, n in c.items() if k.endswith("|5xx")))
        for h, c in zip(names, found, strict=True)
    ]
    return Http(
        total=sum(r.total for r in routes), c5xx=sum(r.c5xx for r in routes), routes=routes[:ROUTES], hourly=hourly
    )


def _middle(seconds: list[float]) -> tuple[float | None, float | None]:
    if not seconds:
        return None, None
    if len(seconds) == 1:
        return seconds[0], seconds[0]
    cuts = quantiles(seconds, n=100, method="inclusive")
    return round(cuts[49], 2), round(cuts[94], 2)


def job_stats(found: list[adascan.OrgAda]) -> list[JobStat]:
    kinds: dict[str, list[adascan.AdaJob]] = {}
    for job in (j for o in found for j in o.jobs):
        kinds.setdefault(job.kind, []).append(job)
    stats = []
    for kind, jobs in sorted(kinds.items()):
        p50, p95 = _middle([j.seconds for j in jobs if j.state == "done" and j.seconds is not None])
        failed = sum(j.state == "failed" for j in jobs)
        unfinished = sum(j.state not in ("done", "failed") for j in jobs)
        stats.append(
            JobStat(kind=kind, total=len(jobs), failed=failed, unfinished=unfinished, p50_seconds=p50, p95_seconds=p95)
        )
    return stats


async def current_alerts(conn: AsyncConnection, redis: Redis, ada_cloud: bool) -> list[Alert]:
    """The alerts alone, for the dashboard's top."""
    return alerts(
        await latency.http_window(redis, 5),
        await infra.queues(redis),
        ada_cloud,
        await infra.last_tick(redis),
        await latency.window(redis, "read", 5),
        await events_store.open_counts(conn, timedelta(hours=1)),
    )


async def health(conn: AsyncConnection, redis: Redis, ada_cloud: bool) -> Infra:
    return Infra(
        ada_cloud=ada_cloud,
        alerts=await current_alerts(conn, redis, ada_cloud),
        thresholds=THRESHOLDS,
        queues=await infra.queues(redis),
        tick=await infra.last_tick(redis),
        read=await _latency(redis, "read"),
        api=await _latency(redis, "api"),
        http=await _http(redis),
        jobs=job_stats(await adascan.scan(conn, redis)),
        database=await infra.database(conn),
        redis=await infra.memory(redis),
    )
