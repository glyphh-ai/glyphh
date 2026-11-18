"""What needs a person now, worked out as staff look (never stored): the thresholds below against the server's own
measures (admin/infra.py, obs/latency.py) and its open ops events (obs/events_store.py)."""

from typing import Literal

from pydantic import BaseModel

from glyphh_server.admin.infra import Tick
from glyphh_server.obs.latency import Endpoint

THRESHOLDS: dict[str, float] = {
    "http_5xx_share": 0.05,  # of the last 5 minutes' requests, once there are http_min of them
    "http_min": 20,
    "tick_seconds": 300,  # since the minute tick last began
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


def _tick(last: Tick) -> list[Alert]:
    if last.age_seconds is not None and last.age_seconds < THRESHOLDS["tick_seconds"]:
        return []
    since = "has not run" if last.age_seconds is None else f"last ran {int(last.age_seconds // 60)} minutes ago"
    return [Alert(code="tick_late", severity="critical", message=f"The minute tick {since}.")]


def _errors(open_counts: dict[str, int]) -> list[Alert]:
    errors = open_counts.get("error", 0) + open_counts.get("critical", 0)
    if errors < THRESHOLDS["open_errors"]:
        return []
    severity: Literal["warning", "critical"] = "critical" if errors >= THRESHOLDS["open_errors_critical"] else "warning"
    return [Alert(code="errors", severity=severity, message=f"{errors} errors not acknowledged in the last hour.")]


def alerts(http_5m: list[Endpoint], last: Tick, open_counts: dict[str, int]) -> list[Alert]:
    found = _http(http_5m) + _tick(last) + _errors(open_counts)
    return sorted(found, key=lambda a: a.severity != "critical")
