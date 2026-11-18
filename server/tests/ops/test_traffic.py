"""The hourly traffic pull against a fake Cloudflare: what it keeps from each dataset, what a plan's limits or the token
let it have (kept as notes on the zone), and the failures that stop it (a warning, never a crash)."""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import TrafficDay, TrafficTop, TrafficZone
from glyphh_server.ops import tend
from glyphh_server.ops.cloudflare import Cloudflare, CloudflareError
from glyphh_server.ops.traffic import pull, queries, store
from glyphh_server.ops.traffic.queries import Limits
from glyphh_server.ops.traffic.rum import NO_PAGE_LOADS
from tests.cloudflare import FIELDS, TOKEN, FakeCloudflare, cloudflare_http, zone

NOW: datetime = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
TODAY: date = NOW.date()


@pytest.fixture
async def clean(engine: AsyncEngine) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        for table in (TrafficZone, TrafficDay, TrafficTop):
            await conn.execute(delete(table))
    yield


async def _pull(engine: AsyncEngine, fake: FakeCloudflare) -> None:
    await pull.pull(engine, Cloudflare(cloudflare_http(fake), TOKEN), NOW)


async def _kept(engine: AsyncEngine) -> tuple[dict[str, Any], dict[tuple[Any, ...], int], dict[tuple[Any, ...], int]]:
    async with engine.connect() as conn:
        zones = {z.name: z for z in await conn.execute(select(TrafficZone.__table__))}
        days = {(r.zone, r.host, r.day, r.metric): r.n for r in await conn.execute(select(TrafficDay.__table__))}
        tops = {(r.zone, r.host, r.day, r.kind, r.key): r.n for r in await conn.execute(select(TrafficTop.__table__))}
    return zones, days, tops


async def test_a_pull_keeps_each_zones_days_hosts_countries_pages_and_referrers(
    engine: AsyncEngine, clean: None
) -> None:
    fake = FakeCloudflare()
    await _pull(engine, fake)
    zones, days, tops = await _kept(engine)
    assert sorted(zones) == ["glyphh.ai", "glyphh.app"]
    ai = zones["glyphh.ai"]
    assert ai.zone_id == "z-ai" and ai.plan == "Free Website" and ai.pulled_at == NOW
    assert ai.available["daily"] == {"ok": True, "days": 60}
    assert ai.available["hosts"] == ai.available["pages"] == ai.available["referrers"] == {"ok": True, "days": 3}
    assert ai.available["rum"] == {"ok": True, "days": 7}
    assert days[("glyphh.ai", "", TODAY, "uniques")] == 10 and days[("glyphh.ai", "", TODAY, "page_views")] == 40
    assert days[("glyphh.ai", "", TODAY, "cached_requests")] == 25
    assert days[("glyphh.ai", "glyphh.ai", TODAY, "requests")] == 50
    assert days[("glyphh.ai", "docs.glyphh.ai", TODAY, "visits")] == 2
    assert days[("glyphh.ai", "docs.glyphh.ai", TODAY, "requests")] == 8 + 2  # its port and capitals folded in
    assert {k[1] for k in days} == {"", "glyphh.ai", "docs.glyphh.ai"}  # another site's Host header left out
    assert tops[("glyphh.ai", "", TODAY, "country", "GB")] == 60
    assert tops[("glyphh.ai", "glyphh.ai", TODAY, "page", "/")] == 30
    assert tops[("glyphh.ai", "docs.glyphh.ai", TODAY, "page", "/")] == 5  # no path: the root
    assert tops[("glyphh.ai", "glyphh.ai", TODAY, "referrer", "www.google.com")] == 9
    assert tops[("glyphh.ai", "glyphh.ai", TODAY, "rum_page", "/pricing")] == 4
    assert ("glyphh.app", "glyphh.ai", TODAY, "rum_page", "/pricing") not in tops  # another zone's host
    pages = next(q for q, _ in fake.queries if "clientRequestPath" in q)
    assert 'edgeResponseContentTypeName: "html"' in pages
    daily = next(v for q, v in fake.queries if "httpRequests1dGroups(" in q)
    assert daily["since"] == str(TODAY - timedelta(days=59)) and daily["until"] == str(TODAY)


async def test_the_daily_totals_are_replaced_and_the_windowed_numbers_keep_the_larger(
    engine: AsyncEngine, clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store, "CHUNK", 2)  # many statements, each a few rows
    fake = FakeCloudflare()
    fake.scale = 3
    await _pull(engine, fake)
    fake.scale = 1
    await _pull(engine, fake)
    _, days, tops = await _kept(engine)
    assert days[("glyphh.ai", "glyphh.ai", TODAY, "requests")] == 150
    assert tops[("glyphh.ai", "glyphh.ai", TODAY, "page", "/")] == 90
    assert days[("glyphh.ai", "", TODAY, "requests")] == 100


async def test_what_a_free_plan_doesnt_allow_is_noted_not_failed(engine: AsyncEngine, clean: None) -> None:
    fake = FakeCloudflare()
    fake.zones = [zone("z-ai", "glyphh.ai", account=None)]
    fake.adaptive = {"enabled": True, "notOlderThan": 86_400, "availableFields": ["clientRequestHTTPHost"]}
    fake.daily_settings = {"enabled": True, "notOlderThan": 7 * 86_400}
    await _pull(engine, fake)
    zones, days, _ = await _kept(engine)
    avail = zones["glyphh.ai"].available
    assert avail["daily"] == {"ok": True, "days": 7}
    assert avail["hosts"] == {"ok": True, "days": 1}
    assert avail["pages"] == avail["referrers"] == {"ok": False, "note": pull.NOT_ON_PLAN}
    assert avail["rum"] == {"ok": False, "note": "No account on this zone"}
    assert ("glyphh.ai", "glyphh.ai", TODAY, "requests") in days

    fake.adaptive = {"enabled": False}
    fake.daily_settings = {"enabled": False}
    await _pull(engine, fake)
    avail = (await _kept(engine))[0]["glyphh.ai"].available
    assert avail["daily"] == avail["hosts"] == {"ok": False, "note": pull.NOT_ON_PLAN}


async def test_a_refused_dataset_is_noted_in_cloudflares_words(
    engine: AsyncEngine, clean: None, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeCloudflare()
    fake.refuse = {
        "settings": "settings: not authorized",
        "rum": "not authorized for that account",
        "pages": "unknown field clientRequestPath",
        "daily": "zone analytics: not authorized",
    }
    await _pull(engine, fake)
    avail = (await _kept(engine))[0]["glyphh.ai"].available
    assert avail["limits"] == {"ok": False, "note": "settings: not authorized"}
    assert avail["rum"] == {"ok": False, "note": "not authorized for that account"}
    assert avail["pages"] == {"ok": False, "note": "unknown field clientRequestPath"}
    assert avail["daily"]["ok"] is False and avail["hosts"]["ok"] is True
    assert "traffic daily totals refused: zone analytics: not authorized" in caplog.text


async def test_a_referrer_given_as_a_whole_url_is_kept_as_its_host(engine: AsyncEngine, clean: None) -> None:
    fake = FakeCloudflare()
    fake.adaptive = {"availableFields": ["clientRequestHTTPHost", "clientRequestReferer"]}
    fake.zones = [zone("z-ai", "glyphh.ai")]
    await _pull(engine, fake)
    _, _, tops = await _kept(engine)
    assert tops[("glyphh.ai", "glyphh.ai", TODAY, "referrer", "www.google.com")] == 9
    assert all(k[4] for k in tops)  # an empty referrer is no referrer
    fake.adaptive = {"enabled": True, "notOlderThan": 86_400, "availableFields": None}  # not said: everything tried
    await _pull(engine, fake)
    avail = (await _kept(engine))[0]["glyphh.ai"].available
    assert avail["pages"] == avail["referrers"] == {"ok": True, "days": 1}


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        (httpx.Response(403, json={"success": False, "errors": [{"message": "Invalid token"}]}), "auth"),
        (httpx.Response(429, text="slow down"), "rate"),
        (httpx.Response(502, text="<html>bad gateway</html>"), "refused"),
        (httpx.Response(200, json={"data": None, "errors": [{"message": "unknown field: visits"}]}), "query"),
        (httpx.Response(200, json=["not", "an", "object"]), "refused"),
        (httpx.Response(200, json={"data": None, "errors": [{"message": "Rate limit exceeded"}]}), "rate"),
    ],
)
async def test_the_client_says_what_kind_of_failure_it_was(answer: httpx.Response, kind: str) -> None:
    cf = Cloudflare(httpx.AsyncClient(transport=httpx.MockTransport(lambda _: answer)), TOKEN)
    with pytest.raises(CloudflareError) as raised:
        await cf.query("{ viewer }", {})
    assert raised.value.kind == kind and TOKEN not in str(raised.value)


async def test_a_failure_that_stops_the_pull_is_a_warning(
    engine: AsyncEngine, clean: None, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeCloudflare()
    fake.status = 403
    await _pull(engine, fake)
    assert (await _kept(engine))[0] == {}
    warned = [r for r in caplog.records if r.name == "glyphh.traffic" and r.levelno == logging.WARNING]
    assert warned and warned[0].getMessage() == "traffic pull failed: Cloudflare refused the token: Unauthorized"

    def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    await pull.pull(engine, Cloudflare(httpx.AsyncClient(transport=httpx.MockTransport(down)), TOKEN))
    assert "Cloudflare could not be reached (ConnectError)" in caplog.text


async def test_a_rate_limit_stops_the_pull_at_once(engine: AsyncEngine, clean: None) -> None:
    fake = FakeCloudflare()
    fake.refuse = {"hosts": "Rate limit exceeded"}
    await _pull(engine, fake)
    assert (await _kept(engine))[0] == {}  # the first zone stopped before it was written
    assert not any(v.get("zone") == "z-app" for _, v in fake.queries)


async def test_the_zones_list_is_read_page_by_page(engine: AsyncEngine, clean: None) -> None:
    fake = FakeCloudflare()
    fake.page_size = 1
    fake.refuse = {"rum": "off"}
    await _pull(engine, fake)
    assert sorted((await _kept(engine))[0]) == ["glyphh.ai", "glyphh.app"]


async def test_the_pull_runs_once_an_hour_from_the_tick(engine: AsyncEngine, clean: None, redis: Redis) -> None:
    await redis.delete(pull.KEY)
    fake = FakeCloudflare()
    cf = Cloudflare(cloudflare_http(fake), TOKEN)
    assert await tend.tend(engine, redis, cf)
    asked = len(fake.queries)
    assert asked and sorted((await _kept(engine))[0]) == ["glyphh.ai", "glyphh.app"]
    assert not await pull.hourly(engine, redis, cf)
    assert len(fake.queries) == asked and 0 < await redis.ttl(pull.KEY) <= pull.EVERY
    await redis.delete(pull.KEY)


async def test_a_long_window_keeps_each_row_on_its_own_day(engine: AsyncEngine, clean: None) -> None:
    fake = FakeCloudflare()
    fake.adaptive = {"notOlderThan": 31 * 86_400, "maxDuration": 30 * 86_400, "availableFields": FIELDS}
    fake.page_loads = False
    await _pull(engine, fake)
    zones, days, tops = await _kept(engine)
    month_ago = str(TODAY - timedelta(days=30))
    assert days[("glyphh.ai", "glyphh.ai", TODAY, "requests")] == 50
    assert days[("glyphh.ai", "glyphh.ai", date.fromisoformat(month_ago), "requests")] == 50  # the second window's
    assert zones["glyphh.ai"].available["hosts"] == {"ok": True, "days": 31}
    assert zones["glyphh.ai"].available["rum"] == {"ok": False, "note": NO_PAGE_LOADS}
    assert not [k for k in tops if k[3].startswith("rum_")]
    assert all("date" in q for q, _ in fake.queries if "httpRequestsAdaptiveGroups(" in q)


def test_the_windows_fit_the_plan() -> None:
    hourly = Limits(not_older=86_400, max_duration=3_600)
    found = queries.windows(NOW, hourly, 5)
    assert len(found) == 5 and found[0] == (NOW - timedelta(hours=1), NOW)  # the newest first
    assert found[-1] == (NOW - timedelta(hours=5), NOW - timedelta(hours=4))
    two = queries.windows(NOW, Limits(not_older=2 * 86_400), 10)
    assert two == [(NOW - timedelta(days=1), NOW), (NOW - timedelta(days=2, minutes=-5), NOW - timedelta(days=1))]
    pro = queries.windows(NOW, Limits(not_older=31 * 86_400, max_duration=30 * 86_400), 8)
    assert [(end - start).days for start, end in pro] == [30, 0]  # a month, then what is left of the plan's reach
    assert queries.limits({}, Limits(page=7), Limits(page=9)) == (Limits(page=7), Limits(page=9))
    assert queries._limits("off", Limits(page=3)) == Limits(page=3)
    rows = [{"dimensions": {"date": str(TODAY)}, "sum": {"countryMap": [{"requests": 2}]}}]
    by_day, countries = queries.daily(rows)
    assert by_day[(TODAY, "uniques")] == 0 and countries == {(TODAY, "(unknown)"): 2}
