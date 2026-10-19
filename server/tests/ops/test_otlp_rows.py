"""OTLP's records made rows, past what rrotor sends today: levels from the severity's text, bodies that are not
strings, the audit marker as an attribute, times missing or ahead of ours, enum values the proto does not know, and
metrics of every kind."""

import uuid
from datetime import UTC, datetime, timedelta

from opentelemetry.proto.metrics.v1.metrics_pb2 import (
    ExponentialHistogram,
    ExponentialHistogramDataPoint,
    Metric,
    NumberDataPoint,
    Summary,
    SummaryDataPoint,
)

from glyphh_server.ops.otlp.points import point_rows
from glyphh_server.ops.otlp.rows import level_of, log_rows, span_rows
from glyphh_server.ops.otlp.values import moment, plain
from tests.otlp import SECOND, gauge, log, logs, metrics, resource, span, traces, value

RUNTIME = uuid.uuid4()
NOW = datetime(2026, 10, 19, 9, 0, 30, tzinfo=UTC)
NOW_NS = int(NOW.timestamp()) * SECOND


def one_log(record: object) -> dict[str, object]:
    (row,) = log_rows(logs(resource(RUNTIME), record), RUNTIME, NOW)  # type: ignore[arg-type]
    return row


def test_a_level_comes_from_the_number_else_the_text_else_info() -> None:
    assert [level_of(n) for n in (1, 5, 9, 13, 17, 21, 24)] == [
        "trace",
        "debug",
        "info",
        "warn",
        "error",
        "fatal",
        "fatal",
    ]
    assert one_log(log(severity=0, text="warning"))["level"] == "warn"
    assert one_log(log(severity=0, text="CRITICAL"))["severity"] == 21
    assert one_log(log(severity=0, text="chatty"))["level"] == "info"
    assert one_log(log(severity=99, text=""))["level"] == "info"


def test_a_body_that_is_not_a_string_is_kept_as_json() -> None:
    assert one_log(log({"a": [1, "b"]}))["body"] == '{"a": [1, "b"]}'
    assert one_log(log(None))["body"] == ""
    assert one_log(log(7))["body"] == "7"
    assert len(str(one_log(log("x" * 20_000))["body"])) == 16_384


def test_the_audit_marker_may_be_an_attribute_and_names_a_kind() -> None:
    assert one_log(log(attrs={"event.name": "rrotor.audit.keys.changed"}))["audit"] == "keys.changed"
    assert one_log(log(event="rrotor.audit."))["audit"] is None
    assert one_log(log(event="something.else"))["audit"] is None


def test_times_missing_or_ahead_are_read_sensibly() -> None:
    assert one_log(log(at=0, observed=NOW_NS - SECOND))["at"] == NOW - timedelta(seconds=1)
    assert one_log(log(at=0))["at"] == NOW
    assert one_log(log(at=NOW_NS + 3600 * SECOND))["at"] == NOW
    assert moment(NOW_NS + 60 * SECOND, NOW) == NOW + timedelta(seconds=60)


def test_values_out_of_json_are_made_safe() -> None:
    assert plain(value(float("nan"))) == "nan" and plain(value(float("inf"))) == "inf"
    assert one_log(log(trace=b"\x00" * 16))["trace_id"] is None


def test_a_span_with_kinds_the_proto_does_not_know_and_no_times() -> None:
    (row,) = span_rows(traces(resource(RUNTIME), span(kind=42, status=9, start=0, end=0, trace=b"")), RUNTIME, NOW)
    assert (row["kind"], row["status"], row["started_at"], row["ended_at"], row["trace_id"]) == (
        "unspecified",
        "unspecified",
        NOW,
        NOW,
        "",
    )


def test_every_kind_of_metric_and_the_newest_point_of_a_minute() -> None:
    expo = ExponentialHistogram(data_points=[ExponentialHistogramDataPoint(time_unix_nano=NOW_NS, sum=2.0, count=4)])
    summary = Summary(data_points=[SummaryDataPoint(time_unix_nano=NOW_NS, sum=float("nan"), count=1)])
    unset = Metric(name="unset", gauge=gauge("x", 1).gauge)
    unset.gauge.data_points[0].CopyFrom(NumberDataPoint(time_unix_nano=0))
    found = metrics(
        resource(RUNTIME),
        Metric(name="expo", exponential_histogram=expo),
        Metric(name="summary", summary=summary),
        Metric(name="empty"),
        unset,
        gauge("same", 1.0, NOW_NS),
        gauge("same", 2.0, NOW_NS),
    )
    rows = {r["name"]: r for r in point_rows(found, RUNTIME, NOW)}
    assert set(rows) == {"expo", "summary", "unset", "same"}
    assert (rows["expo"]["kind"], rows["expo"]["value"], rows["expo"]["count"]) == ("histogram", 2.0, 4)
    assert (rows["summary"]["value"], rows["summary"]["count"]) == (None, 1)
    assert (rows["unset"]["value"], rows["unset"]["at"], rows["unset"]["minute"]) == (None, NOW, NOW.replace(second=0))
    assert rows["same"]["value"] == 2.0
