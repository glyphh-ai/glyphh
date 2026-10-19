"""An export request's log records and spans as rows, each with the node its resource names.

A log record is an audit event when its `event_name` (or its `event.name` attribute) is `rrotor.audit.<kind>`: rrotor
sends both its kept audit events (Enterprise) and its `rrotor.audit` log lines (below it) so; `audit` keeps the
kind. Its level is OTLP's severity number named, else read from its severity text, else info."""

import json
import uuid
from datetime import datetime
from typing import Any

from opentelemetry.proto.trace.v1.trace_pb2 import Span, Status

from glyphh_server.ops.otlp.values import attributes, hex_id, moment, node_of, plain, safe

AUDIT: str = "rrotor.audit."
BODY_MAX: int = 16_384
LEVELS: tuple[str, ...] = ("trace", "debug", "info", "warn", "error", "fatal")  # OTLP's severity numbers by fours
BY_TEXT: dict[str, int] = {"TRACE": 1, "DEBUG": 5, "INFO": 9, "WARN": 13, "WARNING": 13, "ERROR": 17}
BY_TEXT |= {"CRITICAL": 21, "FATAL": 21}
INFO: int = 9


def level_of(severity: int) -> str:
    return LEVELS[(severity - 1) // 4]


def _severity(record: Any) -> int:
    number = int(record.severity_number)
    if 1 <= number <= 24:
        return number
    return BY_TEXT.get(record.severity_text.strip().upper(), INFO)


def _body(record: Any) -> str:
    value = plain(record.body)
    text = "" if value is None else value if isinstance(value, str) else json.dumps(value, default=str)
    return text[:BODY_MAX]


def _audit(record: Any, said: dict[str, Any]) -> str | None:
    event = safe(str(record.event_name or said.get("event.name") or ""))
    if not event.startswith(AUDIT):
        return None
    return event.removeprefix(AUDIT) or None


def _log(record: Any, node: str | None, now: datetime) -> dict[str, Any]:
    said = attributes(record.attributes)
    severity = _severity(record)
    at = moment(record.time_unix_nano, now) or moment(record.observed_time_unix_nano, now) or now
    return {
        "node_id": node,
        "at": at,
        "severity": severity,
        "level": level_of(severity),
        "body": _body(record),
        "audit": _audit(record, said),
        "trace_id": hex_id(record.trace_id),
        "span_id": hex_id(record.span_id),
        "attributes": said,
    }


def log_rows(request: Any, runtime_id: uuid.UUID, now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource_logs in request.resource_logs:
        node = node_of(resource_logs.resource, runtime_id)
        for scope in resource_logs.scope_logs:
            rows += [_log(record, node, now) for record in scope.log_records]
    return rows


def _named(enum: Any, value: int, prefix: str) -> str:
    try:
        return str(enum.Name(value)).removeprefix(prefix).lower()
    except ValueError:
        return "unspecified"


def _span(span: Any, node: str | None, now: datetime) -> dict[str, Any]:
    started = moment(span.start_time_unix_nano, now) or now
    return {
        "node_id": node,
        "trace_id": hex_id(span.trace_id) or "",
        "span_id": hex_id(span.span_id) or "",
        "parent_span_id": hex_id(span.parent_span_id),
        "name": safe(span.name),
        "kind": _named(Span.SpanKind, span.kind, "SPAN_KIND_"),
        "started_at": started,
        "ended_at": moment(span.end_time_unix_nano, now) or started,
        "status": _named(Status.StatusCode, span.status.code, "STATUS_CODE_"),
        "attributes": attributes(span.attributes),
    }


def span_rows(request: Any, runtime_id: uuid.UUID, now: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for resource_spans in request.resource_spans:
        node = node_of(resource_spans.resource, runtime_id)
        for scope in resource_spans.scope_spans:
            rows += [_span(span, node, now) for span in scope.spans]
    return rows
