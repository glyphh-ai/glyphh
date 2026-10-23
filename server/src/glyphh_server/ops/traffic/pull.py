"""The hourly traffic pull, a part of the minute tick (ops/tend.py) with GLYPHH_CLOUDFLARE_API_TOKEN set: for every
zone the token sees, its daily totals and countries (the last 60 days, httpRequests1dGroups), and what its plan lets
the adaptive dataset give (httpRequestsAdaptiveGroups, a few days back on Free): each hostname's requests and visits,
its pages and its referrers by day; and, from the account's Web Analytics (ops/traffic/rum.py) when the token may read
it, the pages and referrers its page loads saw. What a plan or the token doesn't allow is kept as a note on the zone
(`available`), shown to staff; a failure that stops the pull (Cloudflare unreachable, the token refused, its rate
limit) or a zone's daily totals refused is a warning, so an ops event. Once an hour across every process: a Redis key
says one has begun."""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.obs.logs import fields
from glyphh_server.ops.cloudflare import Cloudflare, CloudflareError
from glyphh_server.ops.traffic import queries as q
from glyphh_server.ops.traffic import store
from glyphh_server.ops.traffic.queries import DAY, Limits
from glyphh_server.ops.traffic.rum import rum as account_rum

log = logging.getLogger("glyphh.traffic")

KEY: str = "traffic:pulled"
EVERY: int = 3600
DAILY_DAYS: int = 60
MOST_WINDOWS: int = 8  # adaptive queries a part, a pull at most
DAILY: Limits = Limits(not_older=365 * DAY)
ADAPTIVE: Limits = Limits()
REFERRER_FIELDS: tuple[str, ...] = ("clientRefererHost", "clientRequestReferer")
PATHS: dict[str, str] = {"hosts": "clientRequestHTTPHost", "pages": "clientRequestHTTPHost clientRequestPath"}
NOT_ON_PLAN: str = "Not on this zone's plan"
Avail = dict[str, Any]
Rum = tuple[store.Tops, Avail]


def _account(z: dict[str, Any]) -> str:
    return str((z.get("account") or {}).get("id") or "")


async def hourly(engine: AsyncEngine, redis: Redis, cf: Cloudflare, now: datetime | None = None) -> bool:
    """The pull, if no process has begun one this hour: answers whether it ran."""
    if not await redis.set(KEY, "1", nx=True, ex=EVERY):
        return False
    await pull(engine, cf, now)
    return True


async def pull(engine: AsyncEngine, cf: Cloudflare, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    try:
        zones = await cf.zones()
        rum = {a: await account_rum(cf, a, now) for a in sorted({_account(z) for z in zones} - {""})}
        for z in zones:
            await _zone(engine, cf, z, rum.get(_account(z)), now)
    except CloudflareError as err:
        log.warning("traffic pull failed: %s", err, extra=fields(kind=err.kind))


async def _zone(engine: AsyncEngine, cf: Cloudflare, z: dict[str, Any], rum: Rum | None, now: datetime) -> None:
    zone_id, name = z["id"], z["name"]
    avail: Avail = {}
    try:
        daily, adaptive = q.limits(await cf.query(q.LIMITS, {"zone": zone_id}), DAILY, ADAPTIVE)
    except CloudflareError as err:
        avail["limits"], daily, adaptive = q.note(err), DAILY, ADAPTIVE
    days: store.Days = {}
    tops: store.Tops = {}
    avail["daily"] = await _daily(cf, zone_id, daily, now, days, tops)
    more_days: store.Days = {}
    more_tops: store.Tops = {}
    for part in ("hosts", "pages", "referrers"):
        avail[part] = await _adaptive(cf, zone_id, adaptive, part, now, more_days, more_tops)
    rum_tops, avail["rum"] = rum or ({}, {"ok": False, "note": "No account on this zone"})
    more_tops |= {k: n for k, n in rum_tops.items() if k[0] == name or k[0].endswith(f".{name}")}
    async with engine.begin() as conn:
        await store.zone(conn, name, zone_id, (z.get("plan") or {}).get("name"), now, avail)
        await store.days(conn, name, days, keep_larger=False)
        await store.tops(conn, name, tops, keep_larger=False)
        await store.days(conn, name, more_days, keep_larger=True)
        await store.tops(conn, name, more_tops, keep_larger=True)


async def _daily(
    cf: Cloudflare, zone_id: str, limit: Limits, now: datetime, days: store.Days, tops: store.Tops
) -> Avail:
    if not limit.enabled:
        return {"ok": False, "note": NOT_ON_PLAN}
    back = min(DAILY_DAYS, limit.days)
    window = {"zone": zone_id, "since": str(now.date() - timedelta(days=back - 1)), "until": str(now.date())}
    try:
        data = await cf.query(q.DAILY, window)
    except CloudflareError as err:
        found = q.note(err)
        log.warning("traffic daily totals refused: %s", err, extra=fields(zone=zone_id))
        return found
    by_day, countries = q.daily(q.groups(data, "zones", "httpRequests1dGroups"))
    days.update({("", d, m): n for (d, m), n in by_day.items()})
    tops.update({("", d, "country", c): n for (d, c), n in countries.items()})
    return {"ok": True, "days": back}


def _dims(part: str, limit: Limits) -> str | None:
    """The part's dimensions, if the plan has their fields."""
    if not limit.enabled or not limit.has("clientRequestHTTPHost"):
        return None
    if part == "referrers":
        found = [f for f in REFERRER_FIELDS if limit.has(f)]
        return f"clientRequestHTTPHost {found[0]}" if found else None
    return PATHS[part] if part == "hosts" or limit.has("clientRequestPath") else None


async def _adaptive(
    cf: Cloudflare, zone_id: str, limit: Limits, part: str, now: datetime, days: store.Days, tops: store.Tops
) -> Avail:
    dims = _dims(part, limit)
    if dims is None:
        return {"ok": False, "note": NOT_ON_PLAN}
    html = q.HTML if part != "hosts" and limit.has("edgeResponseContentTypeName") else ""
    query = q.ADAPTIVE % {"limit": min(limit.page, 100), "html": html, "dims": dims}
    found_days: store.Days = {}
    found_tops: store.Tops = {}
    for day, start, end in q.windows(now, limit, MOST_WINDOWS):
        try:
            data = await cf.query(query, {"zone": zone_id, "start": q.stamp(start), "end": q.stamp(end)})
        except CloudflareError as err:
            return q.note(err)
        for row in q.groups(data, "zones", "httpRequestsAdaptiveGroups"):
            _row(part, day, row, found_days, found_tops)
    days.update(found_days)
    tops.update(found_tops)
    return {"ok": True, "days": limit.days}


def _add(found: dict[Any, int], key: Any, n: int) -> None:
    found[key] = found.get(key, 0) + n


def _row(part: str, day: date, row: dict[str, Any], days: store.Days, tops: store.Tops) -> None:
    dims, n = row.get("dimensions") or {}, int(row.get("count") or 0)
    host = dims.get("clientRequestHTTPHost") or ""
    if part == "hosts":
        _add(days, (host, day, "requests"), n)
        _add(days, (host, day, "visits"), int((row.get("sum") or {}).get("visits") or 0))
    elif part == "pages":
        _add(tops, (host, day, "page", dims.get("clientRequestPath") or "/"), n)
    elif referer := next((dims[f] for f in REFERRER_FIELDS if dims.get(f)), ""):
        _add(tops, (host, day, "referrer", urlsplit(referer).hostname or referer), n)
