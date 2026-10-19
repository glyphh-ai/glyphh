"""OTLP export requests as rrotor sends them with server-side logging on (its drain.py's `Glyphh`): built from
opentelemetry-proto's own messages, serialized, gzipped and posted with the runtime's token."""

import gzip
import time
import uuid
from typing import Any

import httpx
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, ArrayValue, KeyValue, KeyValueList
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord, ResourceLogs, ScopeLogs
from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    Gauge,
    Histogram,
    HistogramDataPoint,
    Metric,
    NumberDataPoint,
    ResourceMetrics,
    ScopeMetrics,
    Sum,
)
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span, Status

SECOND: int = 1_000_000_000


def now_ns(ago: float = 0.0) -> int:
    return int((time.time() - ago) * SECOND)


def value(v: Any) -> AnyValue:
    if v is None:
        return AnyValue()
    if isinstance(v, bool):
        return AnyValue(bool_value=v)
    if isinstance(v, int):
        return AnyValue(int_value=v)
    if isinstance(v, float):
        return AnyValue(double_value=v)
    if isinstance(v, bytes):
        return AnyValue(bytes_value=v)
    if isinstance(v, list):
        return AnyValue(array_value=ArrayValue(values=[value(x) for x in v]))
    if isinstance(v, dict):
        return AnyValue(kvlist_value=KeyValueList(values=pairs(v)))
    return AnyValue(string_value=str(v))


def pairs(d: dict[str, Any]) -> list[KeyValue]:
    return [KeyValue(key=k, value=value(v)) for k, v in d.items()]


def resource(runtime_id: uuid.UUID | str | None, node: str | None = "rrotor-0", **extra: Any) -> Resource:
    said: dict[str, Any] = {"service.name": "rrotor", "service.version": "3.0.0", **extra}
    if runtime_id is not None:
        said["rrotor.runtime.id"] = str(runtime_id)
    if node is not None:
        said["service.instance.id"] = node
    return Resource(attributes=pairs(said))


def log(body: Any = "hello", severity: int = 9, text: str = "INFO", at: int | None = None, **kw: Any) -> LogRecord:
    """A log record: `event` its event_name, `attrs` its attributes, `trace`/`span` its ids, `observed` its time
    observed."""
    record = LogRecord(
        time_unix_nano=now_ns() if at is None else at,
        observed_time_unix_nano=kw.get("observed", 0),
        severity_number=severity,  # type: ignore[arg-type]
        severity_text=text,
        body=value(body),
        attributes=pairs(kw.get("attrs", {})),
        event_name=kw.get("event", ""),
        trace_id=kw.get("trace", b""),
        span_id=kw.get("span", b""),
    )
    return record


def audit(kind: str, at: int | None = None, **attrs: Any) -> LogRecord:
    """An audit event as rrotor's audit_record makes it: its kind the body, its fields the attributes."""
    return log(kind, 9, "INFO", at, event=f"rrotor.audit.{kind}", attrs={"kind": kind, **attrs})


def logs(res: Resource, *records: LogRecord) -> ExportLogsServiceRequest:
    return ExportLogsServiceRequest(
        resource_logs=[ResourceLogs(resource=res, scope_logs=[ScopeLogs(log_records=list(records))])]
    )


def gauge(name: str, v: float | int, at: int | None = None, unit: str = "1", **attrs: Any) -> Metric:
    point = NumberDataPoint(time_unix_nano=now_ns() if at is None else at, attributes=pairs(attrs))
    if isinstance(v, int):
        point.as_int = v
    else:
        point.as_double = v
    return Metric(name=name, unit=unit, gauge=Gauge(data_points=[point]))


def counter(name: str, v: int, at: int | None = None, **attrs: Any) -> Metric:
    point = NumberDataPoint(time_unix_nano=now_ns() if at is None else at, attributes=pairs(attrs), as_int=v)
    return Metric(name=name, unit="{run}", sum=Sum(data_points=[point], is_monotonic=True))


def histogram(name: str, total: float, count: int, at: int | None = None, **attrs: Any) -> Metric:
    point = HistogramDataPoint(
        time_unix_nano=now_ns() if at is None else at, attributes=pairs(attrs), sum=total, count=count
    )
    return Metric(name=name, unit="s", histogram=Histogram(data_points=[point]))


def metrics(res: Resource, *found: Metric) -> ExportMetricsServiceRequest:
    return ExportMetricsServiceRequest(
        resource_metrics=[ResourceMetrics(resource=res, scope_metrics=[ScopeMetrics(metrics=list(found))])]
    )


def span(name: str = "POST /v1/run", kind: int = 2, status: int = 1, **kw: Any) -> Span:
    start = kw.get("start", now_ns(0.5))
    return Span(
        trace_id=kw.get("trace", b"\x01" * 16),
        span_id=kw.get("span", b"\x02" * 8),
        parent_span_id=kw.get("parent", b""),
        name=name,
        kind=kind,  # type: ignore[arg-type]
        start_time_unix_nano=start,
        end_time_unix_nano=kw.get("end", start + SECOND // 4),
        status=Status(code=status),  # type: ignore[arg-type]
        attributes=pairs(kw.get("attrs", {})),
    )


def traces(res: Resource, *spans: Span) -> ExportTraceServiceRequest:
    return ExportTraceServiceRequest(
        resource_spans=[ResourceSpans(resource=res, scope_spans=[ScopeSpans(spans=list(spans))])]
    )


async def send(
    client: httpx.AsyncClient, signal: str, message: Any, token: str | None, *, zipped: bool = True, **headers: str
) -> httpx.Response:
    raw = message.SerializeToString() if hasattr(message, "SerializeToString") else message
    sent = {"content-type": "application/x-protobuf"}
    if zipped:
        raw, sent["content-encoding"] = gzip.compress(raw), "gzip"
    if token is not None:
        sent["authorization"] = f"Bearer {token}"
    return await client.post(f"/v1/otlp/v1/{signal}", content=raw, headers=sent | headers)
