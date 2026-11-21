"""What needs a person now, worked out as staff look (never stored): the thresholds below against the server's own
measures (admin/infra.py, obs/latency.py) and its open ops events (obs/events_store.py)."""

from typing import Literal

from pydantic import BaseModel

from glyphh_server.admin.infra import Queue, Tick
from glyphh_server.obs.latency import Endpoint, Percentiles

THRESHOLDS: dict[str, float] = {
    "http_5xx_share": 0.05,  # of the last 5 minutes' requests, once there are http_min of them
    "http_min": 20,
    "backlog_sync": 100,  # messages waiting or in hand on a stream
    "backlog_jobs": 20,
    "tick_seconds": 300,  # since the minute tick last began
    "read_p95_ms": 2000,  # Ada reads, the last 5 minutes, once there are http_min of them
    "open_errors": 1,  # open error events, the last hour: warning from this many
    "open_errors_critical": 25,
}


class Alert(BaseModel):
    code: str
    severity: Literal["warning", "critical"]
    message: str


def _http(last_5m: list[Endpoint]) -> list[Alert]:
    total, failed = sum(e.total for e in last_5m), sum(e.c5xx for e in last_5m)
    if total < THRESHOLDS["http_min"] or failed / total < THRESHOLDS["http_5xx_share"]:
        return []
    share = round(100 * failed / total, 1)
    return [Alert(code="http_5xx", severity="critical", message=f"{share}% of requests failed (5xx) in 5 minutes.")]


def _queues(found: list[Queue], ada_cloud: bool) -> list[Alert]:
    alerts = []
    for q in found:
        backlog, base = q.lag + q.pending, q.stream.partition(":")[0]
        if backlog >= THRESHOLDS[f"backlog_{base}"]:
            alerts.append(
                Alert(code=f"backlog_{q.stream}", severity="warning", message=f"{backlog} waiting on {q.stream}.")
            )
        if ada_cloud and q.alive == 0 and q.stream == base:  # a front door with no worker: nothing is answered
            alerts.append(Alert(code=f"no_worker_{q.stream}", severity="critical", message=f"No {q.stream} worker."))
    return alerts


def _tick(last: Tick) -> list[Alert]:
    if last.age_seconds is not None and last.age_seconds < THRESHOLDS["tick_seconds"]:
        return []
    since = "has not run" if last.age_seconds is None else f"last ran {int(last.age_seconds // 60)} minutes ago"
    return [Alert(code="tick_late", severity="critical", message=f"The minute tick {since}.")]


def _reads(last_5m: Percentiles) -> list[Alert]:
    p95 = last_5m.p95 or 0
    if last_5m.n < THRESHOLDS["http_min"] or p95 < THRESHOLDS["read_p95_ms"]:
        return []
    return [Alert(code="read_slow", severity="warning", message=f"Ada reads p95 is {p95:.0f} ms over 5 minutes.")]


def _errors(open_counts: dict[str, int]) -> list[Alert]:
    errors = open_counts.get("error", 0) + open_counts.get("critical", 0)
    if errors < THRESHOLDS["open_errors"]:
        return []
    severity: Literal["warning", "critical"] = "critical" if errors >= THRESHOLDS["open_errors_critical"] else "warning"
    return [Alert(code="errors", severity=severity, message=f"{errors} errors not acknowledged in the last hour.")]


def alerts(
    http_5m: list[Endpoint],
    queues: list[Queue],
    ada_cloud: bool,
    last: Tick,
    reads_5m: Percentiles,
    open_counts: dict[str, int],
) -> list[Alert]:
    found = _http(http_5m) + _queues(queues, ada_cloud) + _tick(last) + _reads(reads_5m) + _errors(open_counts)
    return sorted(found, key=lambda a: a.severity != "critical")
