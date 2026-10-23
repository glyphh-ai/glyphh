"""The GraphQL queries the traffic pull asks Cloudflare (ops/traffic/pull.py), what a zone's plan allows each dataset
(its `settings` node: how far back, how long a window, how many rows, which fields) and the windows that fit."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from glyphh_server.ops.cloudflare import CloudflareError

DAY: int = 86_400

LIMITS: str = """query ($zone: string) { viewer { zones(filter: {zoneTag: $zone}) { settings {
  httpRequests1dGroups { enabled notOlderThan maxDuration maxPageSize }
  httpRequestsAdaptiveGroups { enabled notOlderThan maxDuration maxPageSize availableFields } } } } }"""

DAILY: str = """query ($zone: string, $since: Date, $until: Date) { viewer { zones(filter: {zoneTag: $zone}) {
  httpRequests1dGroups(limit: 100, filter: {date_geq: $since, date_leq: $until}, orderBy: [date_ASC]) {
    dimensions { date } uniq { uniques }
    sum { requests pageViews bytes threats cachedRequests countryMap { clientCountryName requests } } } } } }"""

ADAPTIVE: str = """query ($zone: string, $start: Time, $end: Time) { viewer { zones(filter: {zoneTag: $zone}) {
  httpRequestsAdaptiveGroups(limit: %(limit)d, filter: {datetime_geq: $start, datetime_lt: $end%(html)s},
    orderBy: [count_DESC]) { count sum { visits } dimensions { date %(dims)s } } } } }"""

RUM: str = """query ($account: string, $start: Time, $end: Time) { viewer { accounts(filter: {accountTag: $account}) {
  rumPageloadEventsAdaptiveGroups(limit: 100, filter: {datetime_geq: $start, datetime_lt: $end},
    orderBy: [count_DESC]) { count sum { visits } dimensions { date requestHost %(dim)s } } } } }"""

HTML: str = ', edgeResponseContentTypeName: "html"'
DAILY_METRICS: dict[str, str] = {
    "requests": "requests",
    "pageViews": "page_views",
    "bytes": "bytes",
    "threats": "threats",
    "cachedRequests": "cached_requests",
}


@dataclass(frozen=True)
class Limits:
    """What a plan allows one dataset: `fields` None when Cloudflare didn't say (then every field is tried)."""

    enabled: bool = True
    not_older: int = DAY
    max_duration: int = DAY
    page: int = 100
    fields: frozenset[str] | None = None

    def has(self, field: str) -> bool:
        """Whether the dataset has a dimension: Cloudflare names it `dimensions_<field>` among its fields."""
        return self.fields is None or field in self.fields or f"dimensions_{field}" in self.fields

    @property
    def days(self) -> int:
        return max(1, self.not_older // DAY)


def _limits(found: Any, default: Limits) -> Limits:
    if not isinstance(found, dict):
        return default
    fields = found.get("availableFields")
    return Limits(
        enabled=bool(found.get("enabled", True)),
        not_older=int(found.get("notOlderThan") or default.not_older),
        max_duration=int(found.get("maxDuration") or default.max_duration),
        page=int(found.get("maxPageSize") or default.page),
        fields=frozenset(fields) if fields else None,
    )


def limits(data: dict[str, Any], daily: Limits, adaptive: Limits) -> tuple[Limits, Limits]:
    zone = (data.get("viewer") or {}).get("zones") or [{}]
    found = zone[0].get("settings") or {}
    return _limits(found.get("httpRequests1dGroups"), daily), _limits(found.get("httpRequestsAdaptiveGroups"), adaptive)


def groups(data: dict[str, Any], scope: str, dataset: str) -> list[dict[str, Any]]:
    """The rows of one dataset of the first zone or account."""
    found = (data.get("viewer") or {}).get(scope) or [{}]
    return list(found[0].get(dataset) or [])


def daily(rows: list[dict[str, Any]]) -> tuple[dict[tuple[date, str], int], dict[tuple[date, str], int]]:
    """Each day's numbers (uniques too) and each day's requests by country."""
    days: dict[tuple[date, str], int] = {}
    countries: dict[tuple[date, str], int] = {}
    for row in rows:
        day = date.fromisoformat(row["dimensions"]["date"])
        sums = row.get("sum") or {}
        for field, metric in DAILY_METRICS.items():
            days[(day, metric)] = int(sums.get(field) or 0)
        days[(day, "uniques")] = int((row.get("uniq") or {}).get("uniques") or 0)
        for country in sums.get("countryMap") or []:
            key = country.get("clientCountryName") or "(unknown)"
            countries[(day, key)] = countries.get((day, key), 0) + int(country.get("requests") or 0)
    return days, countries


def windows(now: datetime, limit: Limits, most: int) -> list[tuple[datetime, datetime]]:
    """Back from now as far as the plan reaches, in windows as long as it allows, the newest first: `most` of them.
    They never overlap, so a day's rows from two windows add up."""
    earliest = now - timedelta(seconds=limit.not_older) + timedelta(minutes=5)
    out: list[tuple[datetime, datetime]] = []
    end = now
    while end > earliest and len(out) < most:
        start = max(earliest, end - timedelta(seconds=limit.max_duration))
        out.append((start, end))
        end = start
    return out


def day_of(dims: dict[str, Any], end: datetime) -> date:
    """A row's day, else its window's last."""
    found = dims.get("date")
    return date.fromisoformat(found) if found else (end - timedelta(seconds=1)).date()


def note(err: CloudflareError) -> dict[str, Any]:
    """A part the plan or the token doesn't allow, in Cloudflare's words; anything else stops the pull."""
    if err.kind != "query":
        raise err
    return {"ok": False, "note": str(err)}


def stamp(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
