"""Ops events: every warning or worse a glyphh logger writes, in the API or the tick, put on Redis as it is logged and
moved to Postgres by the tick, alike ones folded with their count; listed and acknowledged by staff."""

import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import AdminAudit, OpsEvent
from glyphh_server.obs import context, events, events_store, tick
from glyphh_server.obs.events import QUEUE, OpsHandler, event, install, kind_of
from glyphh_server.obs.logs import fields
from glyphh_server.ops import tend
from tests.admin.conftest import Admin
from tests.conftest import REDIS_URL, UNREACHABLE_REDIS


def _record(name: str, msg: str, level: int = logging.ERROR, **about: object) -> logging.LogRecord:
    made = logging.LogRecord(name, level, __file__, 1, msg, None, None)
    made.fields = about  # type: ignore[attr-defined]
    return made


def test_each_event_says_what_it_is_about() -> None:
    assert kind_of(_record("glyphh.request", "crashed"), {"path": "/v1/stripe/webhook"}) == "stripe"
    assert kind_of(_record("glyphh.request", "crashed"), {"path": "/v1/me"}) == "crash"
    assert kind_of(_record("glyphh.api", "refused"), {}) == "http"
    assert kind_of(_record("glyphh.billing", "stripe call failed"), {}) == "stripe"
    assert kind_of(_record("glyphh.staff", "staff view refused"), {}) == "staff"
    assert kind_of(_record("glyphh.tick", "tick part failed: %s"), {}) == "tick"  # its logger's name
    assert kind_of(_record("glyphh.traffic", "traffic pull failed: %s"), {}) == "traffic"
    assert events.severity(logging.CRITICAL) == "critical" and events.severity(logging.WARNING) == "warning"
    assert events.severity(logging.ERROR) == "error"


def test_an_event_carries_its_crash_its_org_and_its_trace() -> None:
    try:
        raise ValueError("bad")
    except ValueError:
        crashed = logging.LogRecord("glyphh.request", logging.ERROR, __file__, 1, "crashed", None, sys.exc_info())
    with context.bound(trace="t" * 16, org=str(uuid.UUID(int=7))):
        found = event(crashed)
    assert "ValueError: bad" in found["detail"]["error"]
    assert (found["org"], found["trace"], found["kind"]) == (str(uuid.UUID(int=7)), "t" * 16, "crash")
    assert event(_record("glyphh.x", "m", org="o"))["org"] == "o"
    plain = event(logging.LogRecord("glyphh.x", logging.WARNING, __file__, 1, "m" * 600, None, (None, None, None)))
    assert plain["detail"] == {} and len(plain["message"]) == 500 and plain["severity"] == "warning"


async def test_the_handler_queues_a_glyphh_warning_only(redis: Redis) -> None:
    handler = OpsHandler(REDIS_URL)
    marker = uuid.uuid4().hex
    handler.handle(_record("glyphh.tick", f"failed {marker}"))
    handler.handle(_record("glyphh.tick", f"noted {marker}", logging.INFO))
    handler.handle(_record("uvicorn.error", f"elsewhere {marker}"))
    handler.handle(_record("glyphh.schema", "database kept: GLYPHH_RESET_DATABASE is not set", logging.WARNING))
    queued = [json.loads(line) for line in await redis.lrange(QUEUE, -10, -1)]  # type: ignore[misc]
    assert not [e for e in queued if e["message"].startswith("database kept")]  # the schema step's own note
    mine = [e for e in queued if marker in e["message"]]
    assert [(e["message"], e["severity"], e["kind"]) for e in mine] == [(f"failed {marker}", "error", "tick")]


async def test_the_queue_is_cut_so_a_flood_cannot_fill_redis(redis: Redis, monkeypatch: pytest.MonkeyPatch) -> None:
    await redis.delete(QUEUE)
    monkeypatch.setattr(events, "KEPT", 3)
    handler = OpsHandler(REDIS_URL)
    for n in range(5):
        handler.handle(_record("glyphh.tick", f"flood {n}"))
    kept = [json.loads(line)["message"] for line in await redis.lrange(QUEUE, 0, -1)]  # type: ignore[misc]
    assert kept == ["flood 2", "flood 3", "flood 4"]  # the newest
    await redis.delete(QUEUE)


def test_a_redis_that_is_down_loses_the_event_never_the_log_line() -> None:
    handler = OpsHandler(UNREACHABLE_REDIS)
    handler.handle(_record("glyphh.tick", "failed"))  # no exception
    assert handler.local.busy is False
    handler.local.busy = True
    handler.handle(_record("glyphh.tick", "failed"))  # what Redis's client logs while one is sent: not sent again
    assert handler.local.busy is True


def test_install_replaces_the_handler() -> None:
    first, second = install(REDIS_URL), install(REDIS_URL)
    root = logging.getLogger().handlers
    assert second in root and first not in root


def test_alike_events_fold_into_one_row_with_their_count() -> None:
    org = str(uuid.uuid4())
    line = {"severity": "error", "kind": "tick", "source": "glyphh.tick", "message": "tick part failed: traffic"}
    first = json.dumps(line | {"at": 1_800_000_000.0, "detail": {"n": 1}, "org": None, "trace": "t1"})
    last = json.dumps(line | {"at": 1_800_000_060.0, "detail": {"n": 2}, "org": org, "trace": "t2"})
    other = json.dumps(line | {"at": 1_800_000_030.0, "severity": "warning"})
    [folded, apart] = events_store.fold([first, other, last])
    assert folded == line | {
        "first_at": datetime.fromtimestamp(1_800_000_000, UTC),
        "last_at": datetime.fromtimestamp(1_800_000_060, UTC),
        "count": 2,
        "detail": {"n": 2},
        "org_id": uuid.UUID(org),
        "trace_id": "t2",
    }
    assert (apart["severity"], apart["count"], apart["detail"], apart["org_id"], apart["trace_id"]) == (
        "warning",
        1,
        {},
        None,
        None,
    )


async def test_the_tick_moves_events_to_postgres_folded(engine: AsyncEngine, redis: Redis) -> None:
    await redis.delete(QUEUE)
    marker = uuid.uuid4().hex
    log = logging.getLogger("glyphh.billing")
    install(REDIS_URL)
    for _ in range(3):
        log.warning("stripe call failed %s", marker, extra=fields(path="/v1/stripe/webhook"))
    log.error("other %s", marker)
    logging.getLogger("glyphh.tick").warning("late %s", marker)
    await redis.delete(tick.KEY)
    assert await tend.tend(engine, redis)
    assert await tick.last(redis) is not None
    async with engine.connect() as conn:
        rows = list(await conn.execute(select(OpsEvent).where(OpsEvent.message.contains(marker))))
    by = {r.message.split()[0]: r for r in rows}
    assert (by["stripe"].count, by["stripe"].kind, by["stripe"].severity) == (3, "stripe", "warning")
    assert by["stripe"].detail == {"path": "/v1/stripe/webhook"} and by["stripe"].source == "glyphh.billing"
    assert (by["other"].count, by["other"].kind, by["other"].severity) == (1, "stripe", "error")
    assert (by["late"].kind, by["late"].source) == ("tick", "glyphh.tick")
    assert await redis.llen(QUEUE) == 0  # type: ignore[misc]


async def test_a_drain_takes_every_batch_and_drops_the_old(
    engine: AsyncEngine, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    await redis.delete(QUEUE)
    monkeypatch.setattr(events_store, "BATCH", 2)
    line = {
        "at": time.time(),
        "severity": "warning",
        "kind": "k",
        "source": "glyphh.t",
        "message": f"batched {uuid.uuid4().hex}",
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
        found = select(OpsEvent.count, OpsEvent.org_id).where(OpsEvent.message == line["message"])
        rows = list(await conn.execute(found))
    assert sorted(r.count for r in rows) == [1, 2, 2] and all(r.org_id is None for r in rows)
    await redis.rpush(QUEUE, *[json.dumps(line)] * 4)  # type: ignore[misc]
    assert await events_store.drain(engine, redis) == 4  # whole batches: the list is read until it is empty
    assert await events_store.drain(engine, redis) == 0


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
    acked = await admin.post(f"/events/{first}/ack")
    assert acked.json() == {"acknowledged": 1}
    again = await admin.post(f"/events/{first}/ack")
    assert again.status_code == 404 and again.json()["error"]["event_id"] == str(first)
    shown = (await admin.get("/events", kind=kind, open_only=True)).json()["events"]
    assert [e["message"] for e in shown] == ["three", "two"]
    every = await admin.post("/events/ack", {"kind": kind, "severity": "warning"})
    assert every.json() == {"acknowledged": 1}
    rest = await admin.post("/events/ack", {"kind": kind})
    assert rest.json() == {"acknowledged": 1}
    done = (await admin.get("/events", kind=kind)).json()["events"]
    assert all(e["acknowledged_by"] == admin.staff.email and e["acknowledged_at"] for e in done)
    async with engine.connect() as conn:
        noted = select(AdminAudit.detail).where(
            AdminAudit.staff_user_id == admin.staff.user_id, AdminAudit.action == "adminAckEvents"
        )
        details = [d for (d,) in await conn.execute(noted.order_by(AdminAudit.at))]
    assert [d["acknowledged"] for d in details] == [1, 1]  # how many each took, kept on its audit row
    assert (await admin.get("/events", severity="fatal")).status_code == 422


async def test_events_come_a_page_at_a_time(admin: Admin, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events_store, "PAGE", 2)
    kind = f"p{uuid.uuid4().hex[:8]}"
    for n in range(3):
        await _event(engine, "warning", kind, f"n{n}")
    page = (await admin.get("/events", kind=kind)).json()
    assert len(page["events"]) == 2 and page["next_before"]
    rest = (await admin.get("/events", kind=kind, before=page["next_before"])).json()
    assert [e["message"] for e in rest["events"]] == ["n0"]


async def test_open_errors_raise_an_alert(admin: Admin, engine: AsyncEngine) -> None:
    await _event(engine, "critical", "crash", "alerting")
    errors = [a for a in (await admin.get("/alerts")).json() if a["code"] == "errors"]
    assert errors and errors[0]["message"].endswith("errors not acknowledged in the last hour.")
    async with engine.begin() as conn:
        counted = await events_store.open_counts(conn, timedelta(hours=1))
        await events_store.acknowledge(conn, "support@glyphh.ai")
        assert counted["critical"] >= 1 and await events_store.open_counts(conn, timedelta(hours=1)) == {}
    assert "errors" not in [a["code"] for a in (await admin.get("/alerts")).json()]
