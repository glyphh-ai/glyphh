"""What the server measures of itself: every request's route, status and time, in Redis by minute and hour, read back
as percentiles and by route; Postgres, Redis and the tick; and the alerts they raise. What the retired products
showed here (Ada's queues, read latency and jobs) is answered empty."""

import asyncio
import time
import uuid
from collections import Counter

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.admin import infra
from glyphh_server.admin.alerts import THRESHOLDS, alerts
from glyphh_server.admin.infra import Tick
from glyphh_server.db.signals import make_redis
from glyphh_server.obs import latency, metrics, tick
from glyphh_server.obs.latency import Endpoint, Percentiles
from glyphh_server.obs.metrics import KIND, Recorder, minute_of
from tests.admin.conftest import Admin
from tests.conftest import UNREACHABLE_REDIS

AT: float = 1_900_000_000.0  # a minute of its own, far from now: no other test's requests in it
ORG: str = "/v1/admin/orgs/{org_id}"
NONE: dict[str, object] = {"n": 0, "p50": None, "p95": None, "p99": None, "mean": None}


async def _clear(redis: Redis, at: float) -> None:
    """A run before this one left its counts for 7 days."""
    minute = minute_of(at)
    kept = [f"ops:{k}:{p}" for k in ("lat:api", "http") for p in (f"m:{minute}", f"h:{minute[:10]}")]
    await redis.delete(*kept)


async def test_a_flush_puts_each_minute_and_hour_in_redis(redis: Redis) -> None:
    await _clear(redis, AT)
    rec = Recorder()
    rec.observe("GET", ORG, 200, 7.0, at=AT)
    rec.observe("GET", ORG, 200, 40.0, at=AT)
    rec.observe("GET", ORG, 500, 20_000.0, at=AT)
    rec.observe("GET", "/v1/me", 404, 3.0, at=AT)
    assert await rec.flush(redis) == 4 and await rec.flush(redis) == 0
    minute = minute_of(AT)
    assert KIND == "api"  # every request is the API's: the one kind left
    timed = await redis.hgetall(f"ops:lat:api:m:{minute}")
    assert timed == {"0": "1", "1": "1", "3": "1", "11": "1", "n": "4", "ms": str(7 + 40 + 20_000 + 3)}
    assert await redis.hgetall(f"ops:lat:api:h:{minute[:10]}") == timed
    assert 0 < await redis.ttl(f"ops:lat:api:m:{minute}") <= metrics.MINUTE_TTL
    assert metrics.MINUTE_TTL < await redis.ttl(f"ops:lat:api:h:{minute[:10]}") <= metrics.HOUR_TTL
    http = await redis.hgetall(f"ops:http:h:{minute[:10]}")
    assert http[f"GET {ORG}|5xx"] == "1" and http["GET /v1/me|4xx"] == "1"
    window = await latency.window(redis, KIND, 1, now=AT)
    assert (window.n, window.p50, window.p99, window.mean) == (4, 10.0, 10_000.0, 5012.5)
    assert (await latency.window(redis, KIND, 1, now=AT - 60)).n == 0  # the minute before
    [(hour, hourly)] = await latency.hourly(redis, KIND, 1, now=AT)
    assert hour == minute[:10] and hourly.n == 4
    routes = await latency.http_window(redis, 1, now=AT)
    assert [(e.method, e.route, e.total, e.c4xx, e.c5xx) for e in routes] == [
        ("GET", ORG, 3, 0, 1),
        ("GET", "/v1/me", 1, 1, 0),
    ]


def test_percentiles_with_no_requests_are_none() -> None:
    assert latency.summary(Counter()) == Percentiles(n=0, p50=None, p95=None, p99=None, mean=None)
    assert latency.percentile(Counter({"n": 2, "0": 2}), 0.5) == 2.5
    assert latency.percentile(Counter({"n": 2, "0": 1, "4": 1}), 0.95) == 95.0  # interpolated in its own bucket
    assert latency.hours(2, now=AT) == [minute_of(AT - 3600)[:10], minute_of(AT)[:10]]  # the oldest first
    assert latency.minutes(2, now=AT) == [minute_of(AT), minute_of(AT - 60)]


async def test_every_request_is_counted_by_its_route(admin: Admin, redis: Redis) -> None:
    await admin.get("/plans")
    await admin.get(f"/orgs/{admin.staff.org_id}")
    await admin.http.get("/no/such/path")
    await admin.http._transport.app.state.metrics.flush(redis)  # type: ignore[attr-defined]
    seen = latency.added(await latency.hashes(redis, (f"ops:http:m:{m}" for m in latency.minutes(2))))
    assert seen["GET /v1/admin/plans|2xx"] >= 1 and seen["GET unmatched|4xx"] >= 1
    assert seen[f"GET {ORG}|2xx"] >= 1  # the route's template, never the org's id


async def test_a_request_that_crashes_is_counted_a_500(redis: Redis) -> None:
    rec = Recorder()

    async def crashing(scope: object, receive: object, send: object) -> None:
        raise RuntimeError("boom")

    counted = metrics.MetricsMiddleware(crashing, rec)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        await counted({"type": "http", "method": "GET"}, None, None)  # type: ignore[arg-type]
    [(minute, counts)] = rec.http.items()
    assert counts == {"GET unmatched|5xx": 1} and rec.latency[(KIND, minute)]["n"] == 1


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


async def test_postgres_redis_and_the_tick(engine: AsyncEngine, redis: Redis) -> None:
    async with engine.connect() as conn:
        db = await infra.database(conn)
    assert db.size_bytes > 0 and db.max_connections > 0 and sum(db.connections.values()) >= 1
    assert db.tables and {"orgs", "users"} & {t.name for t in db.tables} and db.ada_bytes == 0
    assert [t.bytes for t in db.tables] == sorted((t.bytes for t in db.tables), reverse=True)
    memory = await infra.memory(redis)
    assert memory.used_bytes > 0 and memory.peak_bytes > 0 and memory.max_bytes >= 0 and memory.keys >= 0
    await redis.delete(tick.KEY)
    assert await tick.last(redis) is None
    assert await infra.last_tick(redis) == Tick(last_at=None, age_seconds=None)
    await tick.beat(redis, now=time.time() - 30)
    assert 29 <= ((await infra.last_tick(redis)).age_seconds or 0) <= 60
    await tick.beat(redis)
    assert (await infra.last_tick(redis, now=time.time() + 10)).age_seconds == pytest.approx(10, abs=2)


FRESH = Tick(last_at=None, age_seconds=5)


def test_nothing_wrong_raises_nothing() -> None:
    assert alerts([], FRESH, {}) == []
    assert alerts([], FRESH, {"warning": 40}) == []  # warnings alone are no alert


def test_each_threshold_raises_its_alert() -> None:
    failing = [Endpoint(method="GET", route="/x", total=100, c4xx=0, c5xx=10)]
    found = alerts(failing, Tick(last_at=None, age_seconds=None), {"error": 3, "warning": 9})
    assert [(a.code, a.severity, a.message) for a in found] == [
        ("http_5xx", "critical", "10.0% of requests failed (5xx) in 5 minutes."),
        ("tick_late", "critical", "The minute tick has not run."),
        ("errors", "warning", "3 errors not acknowledged in the last hour."),
    ]
    late = alerts([], Tick(last_at=None, age_seconds=600), {"critical": 20, "error": 10})
    assert [(a.code, a.message, a.severity) for a in late] == [
        ("tick_late", "The minute tick last ran 10 minutes ago.", "critical"),
        ("errors", "30 errors not acknowledged in the last hour.", "critical"),
    ]
    assert [a.severity for a in alerts(failing, FRESH, {"error": 1})] == ["critical", "warning"]


def test_few_requests_raise_no_rate_alert() -> None:
    few = [Endpoint(method="GET", route="/x", total=5, c4xx=0, c5xx=5)]
    calm = [Endpoint(method="GET", route="/x", total=500, c4xx=0, c5xx=1)]
    assert alerts(few, FRESH, {}) == alerts(calm, FRESH, {}) == []


async def test_the_infra_page_and_the_alerts(admin: Admin, redis: Redis) -> None:
    await redis.delete(tick.KEY)
    res = await admin.get("/infra")
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["api"]["hourly"]) == 24 and len(body["http"]["hourly"]) == 24
    assert set(body["api"]["last_5m"]) == set(body["api"]["last_hour"]) == set(NONE)
    # The total is every route's; only the 30 busiest are listed.
    assert body["http"]["total"] >= sum(r["total"] for r in body["http"]["routes"]) >= 1
    assert body["http"]["total"] >= body["http"]["c5xx"]
    assert body["database"]["size_bytes"] > 0 and body["redis"]["used_bytes"] > 0
    assert body["tick"] == {"last_at": None, "age_seconds": None}
    assert "tick_late" in [a["code"] for a in body["alerts"]] and body["thresholds"] == THRESHOLDS
    await tick.beat(redis)
    assert "tick_late" not in [a["code"] for a in (await admin.get("/alerts")).json()]
    assert (await admin.get("/infra")).json()["tick"]["age_seconds"] < 60


async def test_what_the_retired_products_showed_is_answered_empty(admin: Admin) -> None:
    body = (await admin.get("/infra")).json()
    assert body["ada_cloud"] is False and body["queues"] == [] and body["jobs"] == []
    assert body["read"] == {"last_5m": NONE, "last_hour": NONE, "hourly": []}
    assert body["database"]["ada_bytes"] == 0


async def test_the_page_counts_the_hours_requests_and_their_failures(admin: Admin, redis: Redis) -> None:
    rec = Recorder()
    counted = f"/v1/counted/{uuid.uuid4().hex}"  # busier than any other route of the hour: among those shown
    for status in (200, 503, 404) * 400:
        rec.observe("GET", counted, status, 12.0)
    await rec.flush(redis)
    body = (await admin.get("/infra")).json()
    [route] = [r for r in body["http"]["routes"] if r["route"] == counted]
    assert (route["method"], route["total"], route["c4xx"], route["c5xx"]) == ("GET", 1200, 400, 400)
    assert len(body["http"]["routes"]) <= 30
    assert body["http"]["c5xx"] >= 400 and sum(h["c5xx"] for h in body["http"]["hourly"]) >= 1
    assert sum(h["total"] for h in body["http"]["hourly"]) >= 3 and body["api"]["last_hour"]["n"] >= 3
    assert body["api"]["hourly"][-1]["latency"]["n"] + body["api"]["hourly"][-2]["latency"]["n"] >= 3
