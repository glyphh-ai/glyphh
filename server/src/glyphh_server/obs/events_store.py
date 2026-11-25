"""Ops events in Postgres: the minute tick moves what the handler put on Redis (obs/events.py) into ops_events, alike
ones (severity, kind, source, message) of one drain folded into one row with their count, and drops those older than
KEPT_DAYS. Staff list them, filtered, and acknowledge them (api/admin/events.py)."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.models import OpsEvent
from glyphh_server.obs.events import QUEUE

BATCH: int = 1000
KEPT_DAYS: int = 30
PAGE: int = 100


class OpsEventView(BaseModel):
    id: uuid.UUID
    first_at: datetime
    last_at: datetime
    severity: str
    kind: str
    source: str
    message: str
    detail: dict[str, Any]
    org_id: uuid.UUID | None
    trace_id: str | None
    count: int
    acknowledged_at: datetime | None
    acknowledged_by: str | None


class OpsEventPage(BaseModel):
    events: list[OpsEventView]
    next_before: datetime | None


def _org(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


def fold(lines: list[str]) -> list[dict[str, Any]]:
    """Alike events as one row each: their first and last time, how many, the last one's detail, org and trace."""
    rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for line in lines:
        e = json.loads(line)
        at = datetime.fromtimestamp(float(e["at"]), UTC)
        key = (e["severity"], e["kind"], e["source"], e["message"])
        row = rows.setdefault(key, {"first_at": at, "count": 0})
        row |= dict(zip(("severity", "kind", "source", "message"), key, strict=True))
        row |= {
            "last_at": at,
            "detail": e.get("detail") or {},
            "org_id": _org(e.get("org")),
            "trace_id": e.get("trace"),
        }
        row["count"] += 1
    return list(rows.values())


async def drain(engine: AsyncEngine, redis: Redis) -> int:
    """What Redis holds moved to Postgres, a batch at a time; answers how many events."""
    moved = 0
    while lines := await redis.lpop(QUEUE, BATCH):  # type: ignore[misc]
        async with engine.begin() as conn:  # no org: the staff's table
            await conn.execute(insert(OpsEvent), fold(lines))
        moved += len(lines)
        if len(lines) < BATCH:
            break
    async with engine.begin() as conn:
        await conn.execute(delete(OpsEvent).where(OpsEvent.last_at < func.now() - timedelta(days=KEPT_DAYS)))
    return moved


def _filtered(found: Any, severity: str | None, kind: str | None, open_only: bool) -> Any:
    if severity:
        found = found.where(OpsEvent.severity == severity)
    if kind:
        found = found.where(OpsEvent.kind == kind)
    if open_only:
        found = found.where(OpsEvent.acknowledged_at.is_(None))
    return found


async def listing(
    conn: AsyncConnection,
    severity: str | None = None,
    kind: str | None = None,
    open_only: bool = False,
    before: datetime | None = None,
) -> OpsEventPage:
    found = _filtered(select(OpsEvent), severity, kind, open_only)
    if before is not None:
        found = found.where(OpsEvent.last_at < before)
    rows = list(await conn.execute(found.order_by(OpsEvent.last_at.desc(), OpsEvent.id).limit(PAGE + 1)))
    events = [OpsEventView(**r._mapping) for r in rows[:PAGE]]
    return OpsEventPage(events=events, next_before=events[-1].last_at if len(rows) > PAGE else None)


async def acknowledge(
    conn: AsyncConnection,
    by: str,
    event_id: uuid.UUID | None = None,
    severity: str | None = None,
    kind: str | None = None,
) -> int:
    """One event, or every open one of a severity and kind, acknowledged; answers how many."""
    found = _filtered(update(OpsEvent), severity, kind, open_only=True)
    if event_id is not None:
        found = found.where(OpsEvent.id == event_id)
    done = await conn.execute(found.values(acknowledged_at=func.now(), acknowledged_by=by).returning(OpsEvent.id))
    return len(done.all())


async def open_counts(conn: AsyncConnection, since: timedelta) -> dict[str, int]:
    """Open events by severity, last seen within `since`: what the alerts count."""
    found = (
        select(OpsEvent.severity, func.sum(OpsEvent.count))
        .where(OpsEvent.acknowledged_at.is_(None), OpsEvent.last_at >= func.now() - since)
        .group_by(OpsEvent.severity)
    )
    return {s: int(n) for s, n in await conn.execute(found)}
