"""Server-side logging is kept GLYPHH_TELEMETRY_RETENTION_DAYS (7 by default, one for every plan): each minute the
tick deletes every log record, audit event, metric point and span older than that, across every org, by the time
each was made (a log record's or point's `at`, a span's start)."""

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import TelemetryLog, TelemetryMetric, TelemetrySpan

TIMES = (
    (TelemetryLog, TelemetryLog.at),
    (TelemetryMetric, TelemetryMetric.at),
    (TelemetrySpan, TelemetrySpan.started_at),
)


async def purge(engine: AsyncEngine, days: int) -> int:
    """Everything past retention deleted; answers how many rows went."""
    cutoff = func.now() - func.make_interval(0, 0, 0, days)
    gone = 0
    async with engine.begin() as conn:  # the connecting role: every org's
        for table, at in TIMES:
            gone += (await conn.execute(delete(table).where(at < cutoff))).rowcount
    return gone
