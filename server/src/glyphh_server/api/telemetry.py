"""What the org's runtimes sent with server-side logging on, for the platform: their log records and audit events,
newest first and paged, and their metrics' latest values. Any member of the org reads them."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops.telemetry import metrics, records
from glyphh_server.ops.telemetry.metrics import Metrics
from glyphh_server.ops.telemetry.records import LIMIT_MAX, Ask, Audit, Level, Logs

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])

Runtime = Annotated[uuid.UUID | None, Query(description="One runtime's only")]
Node = Annotated[str | None, Query(max_length=253, description="One node's only (its node_id)")]
Since = Annotated[datetime | None, Query(description="At or after this instant (RFC 3339)")]
Limit = Annotated[int, Query(ge=1, le=LIMIT_MAX, description="At most this many (1 to 500)")]
Cursor = Annotated[str | None, Query(max_length=200, description="A page's next_cursor: the page after it")]


@router.get("/logs", operation_id="listTelemetryLogs")
async def list_logs(
    caller: Caller,
    conn: Conn,
    runtime: Runtime = None,
    node: Node = None,
    level: Annotated[Level | None, Query(description="This level and above")] = None,
    since: Since = None,
    text: Annotated[str | None, Query(max_length=200, description="In the message, any case")] = None,
    limit: Limit = 100,
    cursor: Cursor = None,
) -> Logs:
    """The org's runtimes' log records, newest first (audit events are at /v1/telemetry/audit)."""
    ask = Ask(runtime, node, since, limit, cursor, level=level, text=text)
    return await records.logs(conn, caller.org_id, ask)


@router.get("/audit", operation_id="listTelemetryAudit")
async def list_audit(
    caller: Caller,
    conn: Conn,
    runtime: Runtime = None,
    node: Node = None,
    kind: Annotated[str | None, Query(max_length=100, description="One kind only: run.call, model.deploy, …")] = None,
    since: Since = None,
    limit: Limit = 100,
    cursor: Cursor = None,
) -> Audit:
    """The org's runtimes' audit events, newest first: who did what and how it ended, never a caller's address."""
    return await records.audit(conn, caller.org_id, Ask(runtime, node, since, limit, cursor, kind=kind))


@router.get("/metrics", operation_id="listTelemetryMetrics")
async def list_metrics(
    caller: Caller,
    conn: Conn,
    runtime: Runtime = None,
    node: Node = None,
    name: Annotated[str | None, Query(max_length=200, description="One metric only: rrotor.runs, …")] = None,
) -> Metrics:
    """The latest value of each metric series the org's runtimes sent, by runtime, node and name."""
    return await metrics.latest(conn, caller.org_id, runtime, node, name)
