"""The staff view's traffic, read from what the hourly pull kept: each zone's and hostname's days, its tops (the
account's own sites left out of referrers), what its plan allowed, and the last 7 and 30 days against the period
before, with the sign-ups in them. Not connected without a Cloudflare token. The public repositories' traffic from
GitHub went with the products: its key is answered not connected, with no repositories."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import Date, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.admin import traffic as admin_traffic
from glyphh_server.admin.traffic import Point, traffic
from glyphh_server.app import create_app
from glyphh_server.models import TrafficDay, TrafficTop, TrafficZone, User
from glyphh_server.ops.traffic import store
from tests.admin.conftest import Admin
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.fakes import fake_http

TODAY: date = datetime.now(UTC).date()
AT: datetime = datetime(2026, 10, 23, 12, tzinfo=UTC)
NO_GITHUB: dict[str, object] = {"connected": False, "repos": []}


@pytest.fixture
async def kept(engine: AsyncEngine) -> AsyncIterator[None]:
    """Two zones as a pull leaves them: glyphh.ai with 60 days, glyphh.app with none yet."""
    async with engine.begin() as conn:
        for table in (TrafficZone, TrafficDay, TrafficTop):
            await conn.execute(delete(table))
        await store.zone(conn, "glyphh.ai", "z-ai", "Free Website", AT, {"pages": {"ok": False, "note": "Not on"}})
        await store.zone(conn, "glyphh.app", "z-app", None, AT - timedelta(hours=1), {})
        days: store.Days = {}
        for back in range(60):
            day = TODAY - timedelta(days=back)
            visitors = 20 if back < 7 else 10
            days |= {("", day, "uniques"): visitors, ("", day, "page_views"): 2 * visitors, ("", day, "requests"): 0}
        days |= {("", TODAY, "requests"): 200, ("", TODAY, "cached_requests"): 50}
        days |= {("docs.glyphh.ai", TODAY, "requests"): 9, ("docs.glyphh.ai", TODAY, "visits"): 4}
        await store.days(conn, "glyphh.ai", days, keep_larger=False)
        tops: store.Tops = {
            ("", TODAY, "country", "GB"): 5,
            ("glyphh.ai", TODAY, "referrer", "www.google.com"): 7,
            ("glyphh.ai", TODAY, "referrer", "docs.glyphh.ai"): 70,
            ("glyphh.ai", TODAY, "referrer", "glyphh.app"): 70,
            ("glyphh.ai", TODAY, "page", "/"): 3,
            ("docs.glyphh.ai", TODAY, "page", "/guide"): 2,
            ("glyphh.ai", TODAY - timedelta(days=40), "page", "/old"): 3,
            ("glyphh.ai", TODAY, "rum_page", "/pricing"): 4,
            ("glyphh.ai", TODAY - timedelta(days=1), "rum_page", "/pricing"): 2,
            ("glyphh.ai", TODAY, "rum_referrer", "news.ycombinator.com"): 6,
            ("glyphh.ai", TODAY, "rum_referrer", "glyphh.ai"): 60,
        }
        await store.tops(conn, "glyphh.ai", tops, keep_larger=False)
    yield


async def _signed_up(engine: AsyncEngine, days: int) -> int:
    joined = cast(User.created_at, Date)
    async with engine.connect() as conn:
        found = select(func.count()).where(joined >= TODAY - timedelta(days=days - 1), joined <= TODAY)
        return int((await conn.execute(found)).scalar_one())


async def test_staff_see_each_zone_its_hosts_and_its_tops(admin: Admin, engine: AsyncEngine, kept: None) -> None:
    res = await admin.get("/traffic", days=7)
    assert res.status_code == 200, res.text
    found = res.json()
    assert found["connected"] is False  # no token in the suite's settings
    assert found["pulled_at"].startswith("2026-10-23T12:00") and found["since"] == str(TODAY - timedelta(days=6))
    assert found["days"] == 7
    ai, app = found["zones"]
    assert (ai["name"], app["name"], app["plan"], app["series"][-1]["uniques"]) == ("glyphh.ai", "glyphh.app", None, 0)
    assert (ai["plan"], app["hosts"], app["available"], app["pages"]) == ("Free Website", [], {}, [])
    assert ai["available"]["pages"]["note"] == "Not on" and len(ai["series"]) == 7
    assert ai["series"][-1] == {
        "day": str(TODAY),
        "requests": 200,
        "page_views": 40,
        "uniques": 20,
        "bytes": 0,
        "threats": 0,
        "cached_share": 0.25,
    }
    assert ai["series"][0]["cached_share"] is None
    assert ai["hosts"] == [
        {
            "host": "docs.glyphh.ai",
            "series": [{"day": str(TODAY - timedelta(days=i)), "requests": 0, "visits": 0} for i in range(6, 0, -1)]
            + [{"day": str(TODAY), "requests": 9, "visits": 4}],
        }
    ]
    assert ai["countries"] == [{"host": "", "key": "GB", "n": 5}]
    assert ai["referrers"] == [{"host": "glyphh.ai", "key": "www.google.com", "n": 7}]  # our own sites left out
    pages = [{"host": "glyphh.ai", "key": "/", "n": 3}, {"host": "docs.glyphh.ai", "key": "/guide", "n": 2}]
    assert ai["pages"] == pages  # the one 40 days back is before the days asked
    assert ai["rum_pages"] == [{"host": "glyphh.ai", "key": "/pricing", "n": 6}]  # its days added up
    assert ai["rum_referrers"] == [{"host": "glyphh.ai", "key": "news.ycombinator.com", "n": 6}]


async def test_the_summary_sets_visitors_against_the_period_before_and_sign_ups(
    admin: Admin, engine: AsyncEngine, kept: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admin_traffic, "TOPS", 1)
    found = (await admin.get("/traffic")).json()
    assert found["days"] == 30 and len(found["zones"][0]["series"]) == 30
    assert [p["key"] for p in found["zones"][0]["pages"]] == ["/"]  # the most kept of each list
    week, month = found["last_7"], found["last_30"]
    assert (week["days"], week["visitors"], week["previous_visitors"], week["page_views"]) == (7, 140, 70, 280)
    assert week["previous_page_views"] == 140
    assert week["visitors_change"] == 1.0 and week["page_views_change"] == 1.0
    assert (month["days"], month["visitors"], month["previous_visitors"]) == (30, 140 + 23 * 10, 300)
    assert month["visitors_change"] == round((370 - 300) / 300, 4)
    assert week["sign_ups"] == await _signed_up(engine, 7)
    assert week["conversion"] == round(week["sign_ups"] / 140, 4)


async def test_github_traffic_went_with_the_products(admin: Admin, kept: None) -> None:
    assert (await admin.get("/traffic", days=7)).json()["github"] == NO_GITHUB


async def test_with_nothing_pulled_there_is_nothing_to_compare(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for table in (TrafficZone, TrafficDay, TrafficTop):
            await conn.execute(delete(table))
        found = await traffic(conn, True, 30, TODAY)
    assert found.github.model_dump() == NO_GITHUB
    assert found.connected and found.pulled_at is None and found.zones == []
    assert found.last_7.visitors == 0 and found.last_7.visitors_change is None and found.last_7.conversion is None
    assert Point(day=TODAY).cached_share is None


async def test_with_a_cloudflare_token_the_page_says_connected(admin: Admin, engine: AsyncEngine) -> None:
    settings = PROVIDER_SETTINGS.model_copy(
        update={"staff_emails": admin.staff.email, "cloudflare_api_token": "cf-test-token"}
    )
    async for http in _client(create_app(settings, http=fake_http())):
        found = await http.get("/v1/admin/traffic", headers=admin.headers)
        assert found.status_code == 200 and found.json()["connected"] is True
        assert found.json()["github"] == NO_GITHUB  # whatever is connected


async def test_the_days_asked_are_bounded(admin: Admin) -> None:
    assert (await admin.get("/traffic", days=0)).status_code == 422
    assert (await admin.get("/traffic", days=367)).status_code == 422
