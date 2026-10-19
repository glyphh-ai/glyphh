"""A decoded export request kept for the runtime its token named, in that runtime's org (row-level security): log
records and spans added, metric points added or, for a series already holding a point that minute, the newer one
kept. The rows are made before anything is written, so a batch refused (another runtime's) leaves nothing."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import TelemetryLog, TelemetryMetric, TelemetrySpan
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.otlp.points import point_rows
from glyphh_server.ops.otlp.rows import log_rows, span_rows

CHUNK: int = 500  # rows a statement: under Postgres's 32,767 parameters at every table's width

Rows = Callable[[Any, Any, datetime], list[dict[str, Any]]]
SIGNALS: dict[str, tuple[Rows, Any]] = {
    "logs": (log_rows, TelemetryLog),
    "metrics": (point_rows, TelemetryMetric),
    "traces": (span_rows, TelemetrySpan),
}


def _points(rows: list[dict[str, Any]]) -> Any:
    made = upsert(TelemetryMetric).values(rows)
    newer = {k: made.excluded[k] for k in ("node_id", "at", "value", "count", "unit", "kind", "received_at")}
    return made.on_conflict_do_update(
        index_elements=[TelemetryMetric.rrotor_id, TelemetryMetric.series, TelemetryMetric.minute],
        set_=newer,
        where=TelemetryMetric.at <= made.excluded.at,
    )


async def _write(conn: AsyncConnection, table: Any, rows: list[dict[str, Any]]) -> None:
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start : start + CHUNK]
        await conn.execute(_points(chunk) if table is TelemetryMetric else insert(table).values(chunk))


async def keep(engine: AsyncEngine, runtime: Runtime, signal: str, request: Any) -> int:
    """The request's records kept; answers how many."""
    make, table = SIGNALS[signal]
    now = datetime.now(UTC)
    rows = [
        {"org_id": runtime.org_id, "rrotor_id": runtime.id, "received_at": now} | row
        for row in make(request, runtime.id, now)
    ]
    if rows:
        async with engine.begin() as conn:
            await tenancy.enter(conn, runtime.org_id)
            await _write(conn, table, rows)
    return len(rows)
