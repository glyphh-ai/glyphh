"""Glyphh's own sites' traffic for staff, from what the hourly pull kept (ops/traffic/pull.py), never Cloudflare itself:
each zone's days (requests, page views, daily unique visitors, bytes, threats, the cached share), each hostname's days
(requests and visits) where its plan gave them, its countries, pages and referrers (the account's own sites left out
of referrers), and what its plan allowed; and the last 7 and 30 days' visitors and page views against the period
before, with the sign-ups in them for a visitor-to-sign-up rate. Visitors are Cloudflare's daily uniques, added up."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import TrafficDay, TrafficTop, TrafficZone, User


class GitHubTraffic(BaseModel):
    connected: bool = False
    repos: list[Any] = []


TOPS: int = 50
METRICS: tuple[str, ...] = ("requests", "page_views", "uniques", "bytes", "threats")
SUMMED: tuple[str, ...] = ("uniques", "page_views")
KINDS: dict[str, str] = {
    "country": "countries",
    "page": "pages",
    "referrer": "referrers",
    "rum_page": "rum_pages",
    "rum_referrer": "rum_referrers",
}


class Point(BaseModel):
    day: date
    requests: int = 0
    page_views: int = 0
    uniques: int = 0
    bytes: int = 0
    threats: int = 0
    cached_share: float | None = None


class HostPoint(BaseModel):
    day: date
    requests: int = 0
    visits: int = 0


class HostSeries(BaseModel):
    host: str
    series: list[HostPoint]


class Top(BaseModel):
    host: str
    key: str
    n: int


class Zone(BaseModel):
    name: str
    plan: str | None
    pulled_at: datetime
    available: dict[str, Any]
    series: list[Point]
    hosts: list[HostSeries]
    countries: list[Top]
    pages: list[Top]
    referrers: list[Top]
    rum_pages: list[Top]
    rum_referrers: list[Top]


class Period(BaseModel):
    days: int
    visitors: int
    page_views: int
    previous_visitors: int
    previous_page_views: int
    visitors_change: float | None
    page_views_change: float | None
    sign_ups: int
    conversion: float | None


class Traffic(BaseModel):
    connected: bool
    pulled_at: datetime | None
    days: int
    since: date
    last_7: Period
    last_30: Period
    zones: list[Zone]
    # The public repositories' traffic from GitHub went with the products; the platform's page still reads the key.
    github: GitHubTraffic = GitHubTraffic()


def _change(now: int, before: int) -> float | None:
    return round((now - before) / before, 4) if before else None


async def _sums(conn: AsyncConnection, since: date, until: date) -> tuple[int, int]:
    q = select(TrafficDay.metric, func.sum(TrafficDay.n)).where(
        TrafficDay.host == "", TrafficDay.day >= since, TrafficDay.day <= until, TrafficDay.metric.in_(SUMMED)
    )
    found = {m: int(n) for m, n in await conn.execute(q.group_by(TrafficDay.metric))}
    return found.get("uniques", 0), found.get("page_views", 0)


async def period(conn: AsyncConnection, days: int, today: date) -> Period:
    since = today - timedelta(days=days - 1)
    visitors, views = await _sums(conn, since, today)
    before_visitors, before_views = await _sums(conn, since - timedelta(days=days), since - timedelta(days=1))
    joined = cast(User.created_at, Date)
    sign_ups = (await conn.execute(select(func.count()).where(joined >= since, joined <= today))).scalar_one()
    return Period(
        days=days,
        visitors=visitors,
        page_views=views,
        previous_visitors=before_visitors,
        previous_page_views=before_views,
        visitors_change=_change(visitors, before_visitors),
        page_views_change=_change(views, before_views),
        sign_ups=sign_ups,
        conversion=round(sign_ups / visitors, 4) if visitors else None,
    )


def _ours(key: str, zones: list[str]) -> bool:
    return any(key == z or key.endswith(f".{z}") for z in zones)


async def _tops(conn: AsyncConnection, since: date, names: list[str]) -> dict[tuple[str, str], list[Top]]:
    total = func.sum(TrafficTop.n)
    keys = (TrafficTop.zone, TrafficTop.kind, TrafficTop.host, TrafficTop.key)
    q = select(*keys, total).where(TrafficTop.day >= since).group_by(*keys)
    rows = await conn.execute(q.order_by(total.desc(), TrafficTop.key, TrafficTop.host))
    found: dict[tuple[str, str], list[Top]] = {}
    for zone, kind, host, key, n in rows:
        if kind in ("referrer", "rum_referrer") and _ours(key, names):
            continue
        listed = found.setdefault((zone, KINDS.get(kind, kind)), [])
        if len(listed) < TOPS:
            listed.append(Top(host=host, key=key, n=int(n)))
    return found


Series = dict[tuple[str, str], dict[date, dict[str, int]]]  # (zone, host) -> day -> metric -> n


async def _series(conn: AsyncConnection, since: date) -> Series:
    keys = (TrafficDay.zone, TrafficDay.host, TrafficDay.day, TrafficDay.metric, TrafficDay.n)
    rows = await conn.execute(select(*keys).where(TrafficDay.day >= since))
    found: Series = {}
    for zone, host, day, metric, n in rows:
        found.setdefault((zone, host), {}).setdefault(day, {})[metric] = int(n)
    return found


def _point(day: date, m: dict[str, int]) -> Point:
    share = round(m["cached_requests"] / m["requests"], 4) if m.get("requests") and "cached_requests" in m else None
    return Point(day=day, cached_share=share, **{k: m.get(k, 0) for k in METRICS})


def _zone(z: Any, every_day: list[date], series: Series, tops: dict[tuple[str, str], list[Top]]) -> Zone:
    hosts = sorted(h for (zone, h) in series if zone == z.name and h)
    by_host = [
        HostSeries(host=h, series=[HostPoint(day=d, **series[(z.name, h)].get(d, {})) for d in every_day])
        for h in hosts
    ]
    return Zone(
        name=z.name,
        plan=z.plan,
        pulled_at=z.pulled_at,
        available=z.available,
        series=[_point(d, series.get((z.name, ""), {}).get(d, {})) for d in every_day],
        hosts=by_host,
        **{name: tops.get((z.name, name), []) for name in KINDS.values()},
    )


async def traffic(conn: AsyncConnection, connected: bool, days: int, today: date | None = None) -> Traffic:
    today = today or datetime.now(UTC).date()
    since = today - timedelta(days=days - 1)
    every_day = [since + timedelta(days=i) for i in range(days)]
    zones = list(await conn.execute(select(TrafficZone.__table__).order_by(TrafficZone.name)))
    series = await _series(conn, since)
    tops = await _tops(conn, since, [z.name for z in zones])
    return Traffic(
        connected=connected,
        pulled_at=max((z.pulled_at for z in zones), default=None),
        days=days,
        since=since,
        last_7=await period(conn, 7, today),
        last_30=await period(conn, 30, today),
        zones=[_zone(z, every_day, series, tops) for z in zones],
    )
