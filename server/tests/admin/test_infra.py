"""What the server measures of itself: every request's route, status and time, in Redis by minute and hour, read back
as percentiles and by route; Ada's queues and workers, Postgres, Redis and the tick; and the alerts they raise."""

import asyncio
import time
import uuid
from collections import Counter

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.admin import adascan, infra
from glyphh_server.admin.alerts import alerts
from glyphh_server.admin.health import job_stats
from glyphh_server.admin.infra import Queue, Tick
from glyphh_server.db.signals import make_redis
from glyphh_server.obs import latency, metrics, tick
from glyphh_server.obs.latency import Endpoint, Percentiles
from glyphh_server.obs.metrics import Recorder, minute_of
from tests.admin.conftest import Admin
from tests.conftest import UNREACHABLE_REDIS

AT: float = 1_900_000_000.0  # a minute of its own, far from now: no other test's requests in it


async def _clear(redis: Redis, at: float) -> None:
    """A run before this one left its counts for 7 days."""
    minute = minute_of(at)
    kinds = [f"ops:lat:{k}:{p}" for k in ("read", "api") for p in (f"m:{minute}", f"h:{minute[:10]}")]
    await redis.delete(*kinds, f"ops:http:m:{minute}", f"ops:http:h:{minute[:10]}")


async def test_a_flush_puts_each_minute_and_hour_in_redis(redis: Redis) -> None:
    await _clear(redis, AT)
    rec = Recorder()
    rec.observe("POST", "/v1/models/{name}/decide", 200, 7.0, at=AT)
    rec.observe("POST", "/v1/models/{name}/decide", 200, 40.0, at=AT)
    rec.observe("POST", "/v1/models/{name}/decide", 500, 20_000.0, at=AT)
    rec.observe("GET", "/v1/me", 404, 3.0, at=AT)
    assert await rec.flush(redis) == 6 and await rec.flush(redis) == 0
    minute = minute_of(AT)
    reads = await redis.hgetall(f"ops:lat:read:m:{minute}")
    assert reads == {"1": "1", "3": "1", "11": "1", "n": "3", "ms": str(7 + 40 + 20_000)}
    assert await redis.hgetall(f"ops:lat:read:h:{minute[:10]}") == reads
    assert 0 < await redis.ttl(f"ops:lat:read:m:{minute}") <= metrics.MINUTE_TTL
    http = await redis.hgetall(f"ops:http:h:{minute[:10]}")
    assert http["POST /v1/models/{name}/decide|5xx"] == "1" and http["GET /v1/me|4xx"] == "1"
    window = await latency.window(redis, "read", 1, now=AT)
    assert (window.n, window.p50, window.p99, window.mean) == (3, 37.5, 10_000.0, round(20_047 / 3, 1))
    [(hour, hourly)] = await latency.hourly(redis, "read", 1, now=AT)
    assert hour == minute[:10] and hourly.n == 3
    routes = await latency.http_window(redis, 1, now=AT)
    assert [(e.method, e.route, e.total, e.c4xx, e.c5xx) for e in routes] == [
        ("POST", "/v1/models/{name}/decide", 3, 0, 1),
        ("GET", "/v1/me", 1, 1, 0),
    ]


def test_percentiles_with_no_requests_are_none() -> None:
    assert latency.summary(Counter()) == Percentiles(n=0, p50=None, p95=None, p99=None, mean=None)
    assert latency.percentile(Counter({"n": 2, "0": 2}), 0.5) == 2.5


async def test_every_request_is_counted_by_its_route(admin: Admin, redis: Redis) -> None:
    await admin.get("/plans")
    await admin.http.get("/no/such/path")
    await admin.http._transport.app.state.metrics.flush(redis)  # type: ignore[attr-defined]
    seen = latency.added(await latency.hashes(redis, (f"ops:http:m:{m}" for m in latency.minutes(2))))
    assert seen["GET /v1/admin/plans|2xx"] >= 1 and seen["GET unmatched|4xx"] >= 1


async def test_the_flush_loop_goes_on_past_a_redis_that_fails() -> None:
    rec = Recorder()
    rec.observe("GET", "/v1/me", 200, 1.0)
    down = make_redis(UNREACHABLE_REDIS)
    task = asyncio.create_task(metrics.flush_forever(rec, down, every=0.01))
    await asyncio.sleep(0.2)
    assert not task.done()
    await metrics.stop(task, rec, down)
    await down.aclose()


async def test_stopping_sends_what_is_left(redis: Redis) -> None:
    await _clear(redis, AT + 3600)
    rec = Recorder()
    task = asyncio.create_task(metrics.flush_forever(rec, redis, every=60))
    rec.observe("GET", "/v1/stop-test", 200, 1.0, at=AT + 3600)
    await metrics.stop(task, rec, redis)
    assert (await redis.hgetall(f"ops:http:m:{minute_of(AT + 3600)}"))["GET /v1/stop-test|2xx"] == "1"


async def test_a_queue_shows_its_backlog_and_live_workers(redis: Redis) -> None:
    stream = f"test:{uuid.uuid4().hex}"
    assert await infra.queue(redis, "sync", stream) == Queue(
        stream="sync", length=0, pending=0, lag=0, consumers=0, alive=0
    )
    await redis.xadd(stream, {"a": "1"})
    assert (await infra.queue(redis, "sync", stream)).length == 1  # a stream with no group yet
    await redis.xgroup_create(stream, "ada", id="0")
    await redis.xadd(stream, {"a": "2"})
    await redis.xreadgroup("ada", "worker-1", {stream: ">"}, count=1)
    found = await infra.queue(redis, "sync", stream)
    assert (found.length, found.pending, found.lag, found.consumers, found.alive) == (2, 1, 1, 1, 1)
    await redis.delete(stream)


async def test_each_kernels_stream_is_shown_beside_the_front_doors(redis: Redis) -> None:
    await redis.xadd("ada:sync:9.9.9", {"a": "1"})
    try:
        names = [q.stream for q in await infra.queues(redis)]
    finally:
        await redis.delete("ada:sync:9.9.9")
    assert names[:2] == ["sync", "jobs"] and "sync:9.9.9" in names


async def test_postgres_redis_and_the_tick(engine: AsyncEngine, redis: Redis) -> None:
    async with engine.connect() as conn:
        db = await infra.database(conn)
    assert db.size_bytes > 0 and db.max_connections > 0 and sum(db.connections.values()) >= 1
    assert db.tables and db.ada_bytes >= 0
    assert (await infra.memory(redis)).used_bytes > 0
    await redis.delete(tick.KEY)
    assert await infra.last_tick(redis) == Tick(last_at=None, age_seconds=None)
    await tick.beat(redis, now=time.time() - 30)
    assert 29 <= ((await infra.last_tick(redis)).age_seconds or 0) <= 60
    await tick.beat(redis)
    assert (await infra.last_tick(redis, now=time.time() + 10)).age_seconds == pytest.approx(10, abs=2)


def _q(stream: str, lag: int = 0, pending: int = 0, alive: int = 1) -> Queue:
    return Queue(stream=stream, length=lag + pending, pending=pending, lag=lag, consumers=alive, alive=alive)


QUIET = Percentiles(n=0, p50=None, p95=None, p99=None, mean=None)
FRESH = Tick(last_at=None, age_seconds=5)


def test_nothing_wrong_raises_nothing() -> None:
    assert alerts([], [_q("sync"), _q("jobs")], True, FRESH, QUIET, {}) == []


def test_each_threshold_raises_its_alert() -> None:
    failing = [Endpoint(method="GET", route="/x", total=100, c4xx=0, c5xx=10)]
    queues = [_q("sync", lag=60, pending=40), _q("jobs", alive=0), _q("sync:3.13.0", lag=500, alive=0)]
    slow = Percentiles(n=50, p50=900, p95=2500, p99=4000, mean=1000)
    found = alerts(failing, queues, True, Tick(last_at=None, age_seconds=None), slow, {"error": 3, "warning": 9})
    assert {a.code: a.severity for a in found} == {
        "http_5xx": "critical",
        "backlog_sync": "warning",
        "no_worker_jobs": "critical",
        "backlog_sync:3.13.0": "warning",
        "tick_late": "critical",
        "read_slow": "warning",
        "errors": "warning",
    }
    assert [a.severity for a in found] == sorted((a.severity for a in found), key=lambda s: s != "critical")
    late = alerts([], [], False, Tick(last_at=None, age_seconds=600), QUIET, {"critical": 30})
    assert [(a.code, a.message, a.severity) for a in late] == [
        ("tick_late", "The minute tick last ran 10 minutes ago.", "critical"),
        ("errors", "30 errors not acknowledged in the last hour.", "critical"),
    ]


def test_few_requests_raise_no_rate_alert() -> None:
    few = [Endpoint(method="GET", route="/x", total=5, c4xx=0, c5xx=5)]
    calm = [Endpoint(method="GET", route="/x", total=500, c4xx=0, c5xx=1)]
    slow_few = Percentiles(n=3, p50=None, p95=9000, p99=None, mean=None)
    assert alerts(few, [], False, FRESH, slow_few, {}) == alerts(calm, [], False, FRESH, QUIET, {}) == []


def test_jobs_by_kind() -> None:
    org = adascan.OrgAda(
        org_id=uuid.uuid4(),
        models=[],
        jobs=[
            adascan.AdaJob(kind="import", state="done", seconds=s, created_at="2026-10-23T00:00:00Z")
            for s in (1.0, 2.0, 3.0, 4.0)
        ]
        + [
            adascan.AdaJob(kind="import", state="failed", seconds=1.0, created_at="2026-10-23T00:00:00Z"),
            adascan.AdaJob(kind="learn", state="done", seconds=5.0, created_at="2026-10-23T00:00:00Z"),
            adascan.AdaJob(kind="export", state="running", seconds=None, created_at="2026-10-23T00:00:00Z"),
        ],
    )
    stats = {s.kind: s for s in job_stats([org])}
    assert (stats["import"].total, stats["import"].failed, stats["import"].p50_seconds) == (5, 1, 2.5)
    assert stats["import"].p95_seconds == 3.85
    assert (stats["learn"].p50_seconds, stats["learn"].p95_seconds) == (5.0, 5.0)
    assert (stats["export"].unfinished, stats["export"].p50_seconds) == (1, None)


async def test_the_infra_page_and_the_alerts(admin: Admin, redis: Redis) -> None:
    await redis.delete(tick.KEY)
    res = await admin.get("/infra")
    assert res.status_code == 200, res.text
    body = res.json()
    assert [q["stream"] for q in body["queues"]][:2] == ["sync", "jobs"]
    assert len(body["read"]["hourly"]) == 24 and len(body["http"]["hourly"]) == 24
    assert body["database"]["size_bytes"] > 0 and body["redis"]["used_bytes"] > 0
    assert "tick_late" in [a["code"] for a in body["alerts"]] and body["thresholds"]["tick_seconds"] == 300
    await tick.beat(redis)
    assert "tick_late" not in [a["code"] for a in (await admin.get("/alerts")).json()]
