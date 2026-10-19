"""The org's log records and audit events as its runtimes sent them, newest first, a page at a time: `next_cursor`
(opaque) reads the page after; null on the last. Log records are those that are not audit events; audit events are
the records rrotor named `rrotor.audit.<kind>`, with their kind."""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import Select, select, tuple_
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import Rrotor, TelemetryLog

Level = Literal["trace", "debug", "info", "warn", "error", "fatal"]
LEAST: dict[str, int] = {"trace": 1, "debug": 5, "info": 9, "warn": 13, "error": 17, "fatal": 21}
LIMIT_MAX: int = 500


class Sent(BaseModel):
    id: uuid.UUID
    at: datetime = Field(description="When it happened, as the node said")
    runtime_id: uuid.UUID
    runtime: str | None = Field(description="The runtime's name")
    node_id: str | None = Field(description="The node it came from (service.instance.id)")
    attributes: dict[str, Any] = Field(description="As sent: rrotor's fields, nested ones dotted (actor.type)")


class LogRecord(Sent):
    level: Level
    severity: int = Field(description="OTLP's severity number, 1 to 24")
    body: str = Field(description="The message")
    trace_id: str | None
    span_id: str | None


class AuditEvent(Sent):
    kind: str = Field(description="run.call, model.deploy, access.denied, …")


class Logs(BaseModel):
    records: list[LogRecord]
    next_cursor: str | None = Field(description="The next page's cursor; null: the last page")


class Audit(BaseModel):
    events: list[AuditEvent]
    next_cursor: str | None = Field(description="The next page's cursor; null: the last page")


@dataclass(frozen=True, slots=True)
class Ask:
    runtime: uuid.UUID | None = None
    node: str | None = None
    since: datetime | None = None
    limit: int = 100
    cursor: str | None = None
    level: Level | None = None  # logs: this level and above
    text: str | None = None  # logs: in the message, any case
    kind: str | None = None  # audit: this kind only


def _cursor(row: Any) -> str:
    return base64.urlsafe_b64encode(f"{row.at.isoformat()}|{row.id}".encode()).decode()


def _after(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, _, row_id = base64.urlsafe_b64decode(cursor.encode()).decode().partition("|")
        return datetime.fromisoformat(at), uuid.UUID(row_id)
    except ValueError:
        raise Invalid("This cursor is not one a page gave.", reason="cursor") from None


def _paged(org_id: uuid.UUID, ask: Ask) -> Select[Any]:
    t = TelemetryLog
    q = select(t, Rrotor.name.label("runtime")).join(Rrotor, Rrotor.id == t.rrotor_id).where(t.org_id == org_id)
    for column, wanted in ((t.rrotor_id, ask.runtime), (t.node_id, ask.node)):
        q = q if wanted is None else q.where(column == wanted)
    if ask.since is not None:
        q = q.where(t.at >= ask.since)
    if ask.cursor is not None:
        q = q.where(tuple_(t.at, t.id) < tuple_(*_after(ask.cursor)))
    return q.order_by(t.at.desc(), t.id.desc()).limit(ask.limit + 1)


async def _page(conn: AsyncConnection, query: Select[Any], limit: int) -> tuple[list[Any], str | None]:
    rows = list(await conn.execute(query))
    return rows[:limit], (_cursor(rows[limit - 1]) if len(rows) > limit else None)


def _escaped(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def logs(conn: AsyncConnection, org_id: uuid.UUID, ask: Ask) -> Logs:
    q = _paged(org_id, ask).where(TelemetryLog.audit.is_(None))
    if ask.level is not None:
        q = q.where(TelemetryLog.severity >= LEAST[ask.level])
    if ask.text:
        q = q.where(TelemetryLog.body.ilike(f"%{_escaped(ask.text)}%", escape="\\"))
    rows, after = await _page(conn, q, ask.limit)
    return Logs(
        records=[LogRecord.model_validate({**r._mapping, "runtime_id": r.rrotor_id}) for r in rows], next_cursor=after
    )


async def audit(conn: AsyncConnection, org_id: uuid.UUID, ask: Ask) -> Audit:
    q = _paged(org_id, ask).where(TelemetryLog.audit.is_not(None))
    if ask.kind is not None:
        q = q.where(TelemetryLog.audit == ask.kind)
    rows, after = await _page(conn, q, ask.limit)
    events = [AuditEvent.model_validate({**r._mapping, "runtime_id": r.rrotor_id, "kind": r.audit}) for r in rows]
    return Audit(events=events, next_cursor=after)
