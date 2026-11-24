"""Ops events: every warning or worse a glyphh logger writes, in the API or a worker, put on Redis as it is logged and
moved to Postgres by the tick, alike ones folded with their count; listed and acknowledged by staff."""

import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OpsEvent
from glyphh_server.obs import context, events, events_store, tick
from glyphh_server.obs.events import QUEUE, OpsHandler, event, install, kind_of
from glyphh_server.obs.logs import fields
from glyphh_server.ops import tend
from tests.admin.conftest import Admin
from tests.conftest import REDIS_URL, SETTINGS, UNREACHABLE_REDIS


def _record(name: str, msg: str, level: int = logging.ERROR, **about: object) -> logging.LogRecord:
    made = logging.LogRecord(name, level, __file__, 1, msg, None, None)
    made.fields = about  # type: ignore[attr-defined]
    return made


def test_each_event_says_what_it_is_about() -> None:
    assert kind_of(_record("glyphh.ada", "job refused: %s"), {}) == "job"
    assert kind_of(_record("glyphh.ada", "failed"), {}) == "worker"
    assert kind_of(_record("glyphh.request", "crashed"), {"path": "/v1/stripe/webhook"}) == "stripe"
    assert kind_of(_record("glyphh.request", "crashed"), {"path": "/v1/me"}) == "crash"
    assert kind_of(_record("glyphh.runtime", "tick part failed: %s"), {}) == "tick"
    assert kind_of(_record("glyphh.runtime", "idle runtime not stopped"), {}) == "runtime"
    assert kind_of(_record("glyphh.github", "github app call failed"), {}) == "github"
    assert events.severity(logging.CRITICAL) == "critical" and events.severity(logging.WARNING) == "warning"


def test_an_event_carries_its_crash_its_org_and_its_trace() -> None:
    try:
        raise ValueError("bad")
    except ValueError:
        import sys

        crashed = logging.LogRecord("glyphh.request", logging.ERROR, __file__, 1, "crashed", None, sys.exc_info())
    with context.bound(trace="t" * 16, org=str(uuid.UUID(int=7))):
        found = event(crashed)
    assert "ValueError: bad" in found["detail"]["error"]
    assert (found["org"], found["trace"], found["kind"]) == (str(uuid.UUID(int=7)), "t" * 16, "crash")
    assert event(_record("glyphh.x", "m", org="o"))["org"] == "o"


async def test_the_handler_queues_a_glyphh_warning_only(redis: Redis) -> None:
    handler = OpsHandler(REDIS_URL)
    marker = uuid.uuid4().hex
    handler.handle(_record("glyphh.ada", f"failed {marker}"))
    handler.handle(_record("glyphh.ada", f"noted {marker}", logging.INFO))
    handler.handle(_record("uvicorn.error", f"elsewhere {marker}"))
    handler.handle(_record("glyphh.ada", "Ada Cloud is off (GLYPHH_ADA_CLOUD): this worker group does nothing", 30))
    queued = [json.loads(line) for line in await redis.lrange(QUEUE, -10, -1)]  # type: ignore[misc]
    mine = [e for e in queued if marker in e["message"]]
    assert [(e["message"], e["severity"]) for e in mine] == [(f"failed {marker}", "error")]


def test_a_redis_that_is_down_loses_the_event_never_the_log_line() -> None:
    handler = OpsHandler(UNREACHABLE_REDIS)
    handler.handle(_record("glyphh.ada", "failed"))  # no exception
    handler.local.busy = True
    handler.handle(_record("glyphh.ada", "failed"))  # what Redis's client logs while one is sent: not sent again


def test_install_replaces_the_handler() -> None:
    first, second = install(REDIS_URL), install(REDIS_URL)
    root = logging.getLogger().handlers
    assert second in root and first not in root


async def test_the_tick_moves_events_to_postgres_folded(engine: AsyncEngine, redis: Redis) -> None:
    await redis.delete(QUEUE)
    marker = uuid.uuid4().hex
    log = logging.getLogger("glyphh.billing")
    install(REDIS_URL)
    for _ in range(3):
        log.warning("stripe call failed %s", marker, extra=fields(path="/v1/stripe/webhook"))
    log.error("other %s", marker)
    await redis.delete(tick.KEY)
    assert await tend.tend(engine, redis, SETTINGS, None)
    assert await tick.last(redis) is not None
    async with engine.connect() as conn:
        rows = list(await conn.execute(select(OpsEvent).where(OpsEvent.message.contains(marker))))
    by = {r.message.split()[0]: r for r in rows}
    assert (by["stripe"].count, by["stripe"].kind, by["stripe"].severity) == (3, "stripe", "warning")
    assert (by["other"].count, by["other"].kind, by["other"].severity) == (1, "stripe", "error")
    assert await redis.llen(QUEUE) == 0  # type: ignore[misc]


async def test_a_drain_takes_every_batch_and_drops_the_old(
    engine: AsyncEngine, redis: Redis, monkeypatch: object
) -> None:
    await redis.delete(QUEUE)
    monkeypatch.setattr(events_store, "BATCH", 2)  # type: ignore[attr-defined]
    line = {
        "at": time.time(),
        "severity": "warning",
        "kind": "k",
        "source": "glyphh.t",
        "message": "batched",
        "detail": {},
    }
    await redis.rpush(QUEUE, *[json.dumps(line | {"org": "not-a-uuid"})] * 5)  # type: ignore[misc]
    old = datetime.now(UTC) - timedelta(days=events_store.KEPT_DAYS + 1)
    async with engine.begin() as conn:
        values = {"first_at": old, "last_at": old, "severity": "error", "kind": "old", "source": "s", "message": "old"}
        aged = (await conn.execute(insert(OpsEvent).values(**values).returning(OpsEvent.id))).scalar_one()
    assert await events_store.drain(engine, redis) == 5
    async with engine.connect() as conn:
        assert (await conn.execute(select(OpsEvent.id).where(OpsEvent.id == aged))).first() is None
        counts = [r.count for r in await conn.execute(select(OpsEvent.count).where(OpsEvent.message == "batched"))]
    assert sorted(counts)[-3:] == [1, 2, 2]


async def _event(engine: AsyncEngine, severity: str, kind: str, message: str) -> uuid.UUID:
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        values = {"first_at": now, "last_at": now, "severity": severity, "kind": kind, "source": "glyphh.t"}
        return (
            await conn.execute(insert(OpsEvent).values(**values, message=message).returning(OpsEvent.id))
        ).scalar_one()


async def test_staff_list_and_acknowledge_events(admin: Admin, engine: AsyncEngine) -> None:
    kind = f"k{uuid.uuid4().hex[:8]}"
    first = await _event(engine, "error", kind, "one")
    await _event(engine, "warning", kind, "two")
    await _event(engine, "critical", kind, "three")
    listed = (await admin.get("/events", kind=kind)).json()
    assert [e["message"] for e in listed["events"]] == ["three", "two", "one"] and listed["next_before"] is None
    assert [e["message"] for e in (await admin.get("/events", kind=kind, severity="error")).json()["events"]] == ["one"]
    acked = await admin.http.post(f"/v1/admin/events/{first}/ack", headers=admin.headers)
    assert acked.json() == {"acknowledged": 1}
    again = await admin.http.post(f"/v1/admin/events/{first}/ack", headers=admin.headers)
    assert again.status_code == 404
    shown = (await admin.get("/events", kind=kind, open_only=True)).json()["events"]
    assert [e["message"] for e in shown] == ["three", "two"]
    every = await admin.http.post(
        "/v1/admin/events/ack", json={"kind": kind, "severity": "warning"}, headers=admin.headers
    )
    assert every.json() == {"acknowledged": 1}
    rest = await admin.http.post("/v1/admin/events/ack", json={"kind": kind}, headers=admin.headers)
    assert rest.json() == {"acknowledged": 1}
    done = (await admin.get("/events", kind=kind)).json()["events"]
    assert all(e["acknowledged_by"] == admin.staff.email for e in done)


async def test_events_come_a_page_at_a_time(admin: Admin, engine: AsyncEngine, monkeypatch: object) -> None:
    monkeypatch.setattr(events_store, "PAGE", 2)  # type: ignore[attr-defined]
    kind = f"p{uuid.uuid4().hex[:8]}"
    for n in range(3):
        await _event(engine, "warning", kind, f"n{n}")
    page = (await admin.get("/events", kind=kind)).json()
    assert len(page["events"]) == 2 and page["next_before"]
    rest = (await admin.get("/events", kind=kind, before=page["next_before"])).json()
    assert [e["message"] for e in rest["events"]] == ["n0"]


async def test_open_errors_raise_an_alert(admin: Admin, engine: AsyncEngine) -> None:
    await _event(engine, "critical", "crash", "alerting")
    codes = [a["code"] for a in (await admin.get("/alerts")).json()]
    assert "errors" in codes
