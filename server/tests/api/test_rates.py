"""Fly's rates, as people see them: Fly's own, and each self-serve paid plan's with its markup in them, a month and a
second; the rate in force the newest that has come; a region with none is unavailable."""

from datetime import date, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import FlyRate
from glyphh_server.ops.rates import in_force
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.fakes import fake_http


async def test_the_rates_are_flys_and_each_paid_plans_all_in(client: httpx.AsyncClient) -> None:
    res = await client.get("/v1/rates")
    assert res.status_code == 200, res.text
    rates = res.json()
    assert (rates["effective_from"], rates["source"], rates["region"]) == (
        "2026-10-18",
        "https://docs.fly.io/about/pricing",
        "iad",
    )
    assert rates["sizes"] == [
        {
            "size": "small",
            "cpu_kind": "shared",
            "cpus": 1,
            "memory_mb": 1024,
            "volume_gb": 3,
            "usd_per_month": 6.7,
            "usd_per_second": 0.0000025849,
        },
        {
            "size": "medium",
            "cpu_kind": "shared",
            "cpus": 2,
            "memory_mb": 4096,
            "volume_gb": 10,
            "usd_per_month": 25.39,
            "usd_per_second": 0.0000097955,
        },
        {
            "size": "large",
            "cpu_kind": "performance",
            "cpus": 2,
            "memory_mb": 8192,
            "volume_gb": 20,
            "usd_per_month": 90.0,
            "usd_per_second": 0.0000347222,
        },
    ]
    assert rates["volume_usd_per_gb_month"] == 0.15
    assert sorted(rates["plans"]) == ["Pro", "Team"]  # Free has no hosting; Enterprise's is in its contract
    pro = rates["plans"]["Pro"]
    assert [(s["size"], s["usd_per_month"], s["usd_per_second"]) for s in pro["sizes"]] == [
        ("small", 8.71, 0.0000033603),
        ("medium", 33.01, 0.0000127353),
        ("large", 117.0, 0.0000451389),
    ]
    assert pro["volume_usd_per_gb_month"] == 0.2 and rates["plans"]["Team"] == pro
    assert "markup" not in res.text


async def test_the_rate_in_force_is_the_newest_that_has_come(engine: AsyncEngine) -> None:
    today = date.today()
    async with engine.begin() as conn:
        for item, usd, when in (
            ("small", "1.00", date(2020, 1, 1)),
            ("small", "2.00", today),
            ("small", "3.00", today + timedelta(days=30)),
            ("volume", "0.10", date(2020, 1, 1)),
        ):
            values = {"item": item, "usd_per_30_days": Decimal(usd), "effective_from": when, "source": "test"}
            await conn.execute(insert(FlyRate).values(region="tst", **values))
    try:
        async with engine.connect() as conn:
            found = await in_force(conn, "tst", today)
            assert found is not None
            assert (found.usd, found.effective_from) == ({"small": Decimal("2.00"), "volume": Decimal("0.10")}, today)
            assert await in_force(conn, "nowhere", today) is None
    finally:
        async with engine.begin() as conn:
            await conn.execute(delete(FlyRate).where(FlyRate.region == "tst"))


async def test_a_region_with_no_rates_is_unavailable(engine: AsyncEngine) -> None:
    elsewhere = PROVIDER_SETTINGS.model_copy(update={"fly_region": "nowhere"})
    async for client in _client(create_app(elsewhere, http=fake_http())):
        res = await client.get("/v1/rates")
        assert (res.status_code, res.json()["error"]["reason"]) == (503, "no_rates")
