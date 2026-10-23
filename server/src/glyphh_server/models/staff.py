"""Glyphh's own tables, for its staff only (row-level security shows them to no session acting for an org): the audit
of every staff request (glyphh_server/admin/audit.py) and the server's own errors and warnings (obs/events.py)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid

SEVERITIES: tuple[str, ...] = ("warning", "error", "critical")


def _at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _detail() -> Mapped[dict[str, Any]]:
    return mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class AdminAudit(Base):
    """One staff request: who made it (the staff member's user and verified email), what (`action`, its `target` and
    `detail`), when, about which org, and how it ended (`ok`, or the refusal's code)."""

    __tablename__ = "admin_audit"
    __table_args__ = (Index("admin_audit_at", "at"), Index("admin_audit_org", "org_id", "at"))

    id: Mapped[uuid.UUID] = guid()
    at: Mapped[datetime] = _at()
    staff_user_id: Mapped[uuid.UUID]
    staff_email: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    org_id: Mapped[uuid.UUID | None]
    target: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = _detail()
    outcome: Mapped[str] = mapped_column(Text, server_default="ok")


class OpsEvent(Base):
    """An error or warning the server logged (a crash, a 5xx, a worker's failure, a tick part's, Stripe's, a job's):
    alike ones (kind, source, message, severity) within one drain folded into one row, `count` of them from `first_at`
    to `last_at`. Acknowledged by a staff member once seen."""

    __tablename__ = "ops_events"
    __table_args__ = (
        CheckConstraint(f"severity IN {SEVERITIES}", name="ops_events_severity"),
        CheckConstraint("count > 0", name="ops_events_count"),
        Index("ops_events_last", "last_at"),
    )

    id: Mapped[uuid.UUID] = guid()
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = _detail()
    org_id: Mapped[uuid.UUID | None]
    trace_id: Mapped[str | None] = mapped_column(Text)
    count: Mapped[int] = mapped_column(server_default="1")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(Text)
