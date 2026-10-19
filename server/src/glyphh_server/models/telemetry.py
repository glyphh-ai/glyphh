"""What a runtime sends with server-side logging on (rrotor's `RROTOR_SERVER_LOGS=on`, docs/specs/cluster.md 7): its
log records (audit events among them, named by `audit`), its metric points and its spans, as OTLP brought them, each
with the org and runtime its token named and the node its `service.instance.id` said. Never inputs, results or a
caller's address: rrotor leaves them out and ops/otlp/values.py drops them again. Kept for
GLYPHH_TELEMETRY_RETENTION_DAYS, purged by the minute tick (ops/telemetry/retention.py)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Double, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid


def _org() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))


def _runtime() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"), index=True)


def _received() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class TelemetryLog(Base):
    """A log record: `at` its time (else when it was observed, else when it came), `severity` OTLP's number (1 to 24;
    `level` its name, trace to fatal), `body` its message; `audit` the event's kind (`run.call`) when the record is an
    audit event (`event_name` `rrotor.audit.<kind>`), else null."""

    __tablename__ = "telemetry_logs"
    __table_args__ = (Index("telemetry_logs_newest", "org_id", "at", "id"), Index("telemetry_logs_at", "at"))

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = _org()
    rrotor_id: Mapped[uuid.UUID] = _runtime()
    node_id: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    audit: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(Text)
    span_id: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = _received()


class TelemetryMetric(Base):
    """A metric's point, at most one per series a minute (the newest that minute): `series` names the node, the metric
    and its point's attributes; `kind` gauge, sum or histogram; `value` a gauge's or sum's value, a histogram's sum,
    with its `count`."""

    __tablename__ = "telemetry_metrics"
    __table_args__ = (
        Index("telemetry_metrics_point", "rrotor_id", "series", "minute", unique=True),
        Index("telemetry_metrics_newest", "org_id", "name", "at"),
        Index("telemetry_metrics_at", "at"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = _org()
    rrotor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"))
    node_id: Mapped[str | None] = mapped_column(Text)
    series: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    minute: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float | None] = mapped_column(Double)
    count: Mapped[int | None] = mapped_column(BigInteger)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = _received()


class TelemetrySpan(Base):
    """A span: its trace, its parent, its name and kind, when it started and ended, its status (`unset`, `ok`,
    `error`) and attributes."""

    __tablename__ = "telemetry_spans"
    __table_args__ = (
        Index("telemetry_spans_newest", "org_id", "started_at"),
        Index("telemetry_spans_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = _org()
    rrotor_id: Mapped[uuid.UUID] = _runtime()
    node_id: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str] = mapped_column(Text)
    span_id: Mapped[str] = mapped_column(Text)
    parent_span_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    received_at: Mapped[datetime] = _received()
