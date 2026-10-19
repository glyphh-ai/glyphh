"""An export request's metric points as rows, one per series a minute.

rrotor reads its metrics every 5 s and sends every series each time (cumulative): kept whole that would be a row per
series every 5 s. So a series (the node, the metric's name and its point's attributes) keeps one point a minute, the
newest: `minute` is its time to the minute, and a later point in the same minute replaces it (keep.py). A gauge's
or a sum's point keeps its value; a histogram's (plain, exponential, or a summary) its sum as `value`, with its
`count`."""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from glyphh_server.ops.otlp.values import attributes, moment, node_of, number, safe

NUMBERS: tuple[str, ...] = ("gauge", "sum")
DISTRIBUTIONS: tuple[str, ...] = ("histogram", "exponential_histogram", "summary")


def series(node: str | None, name: str, said: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps([node, name, said], sort_keys=True, default=str).encode()).hexdigest()


def _value(kind: str, point: Any) -> tuple[float | None, int | None]:
    if kind in NUMBERS:
        which = point.WhichOneof("value")
        return (number(float(getattr(point, which))) if which else None), None
    return number(point.sum), int(point.count)


def _points(metric: Any, node: str | None, now: datetime) -> list[dict[str, Any]]:
    kind = metric.WhichOneof("data")
    if kind not in NUMBERS + DISTRIBUTIONS:
        return []
    name, unit = safe(metric.name), safe(metric.unit)
    rows = []
    for point in getattr(metric, kind).data_points:
        said = attributes(point.attributes)
        at = moment(point.time_unix_nano, now) or now
        value, count = _value(kind, point)
        rows.append(
            {
                "node_id": node,
                "series": series(node, name, said),
                "name": name,
                "unit": unit,
                "kind": "histogram" if kind in DISTRIBUTIONS else kind,
                "minute": at.replace(second=0, microsecond=0),
                "at": at,
                "value": value,
                "count": count,
                "attributes": said,
            }
        )
    return rows


def point_rows(request: Any, runtime_id: uuid.UUID, now: datetime) -> list[dict[str, Any]]:
    """The newest point of each series in each minute the request covers."""
    newest: dict[tuple[str, datetime], dict[str, Any]] = {}
    for resource_metrics in request.resource_metrics:
        node = node_of(resource_metrics.resource, runtime_id)
        for scope in resource_metrics.scope_metrics:
            for metric in scope.metrics:
                for row in _points(metric, node, now):
                    key = (row["series"], row["minute"])
                    if key not in newest or newest[key]["at"] <= row["at"]:
                        newest[key] = row
    return list(newest.values())
