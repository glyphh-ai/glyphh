"""Hosted machines metered per second at Fly's rates, the org's markup (its own over its plan's) in the charge; and
what the org uses: its hosted runtimes' precedents of the plan's bucket and its hosting month to date, machine by
machine, deleted ones too; in the API, /v1/me and the connector's usage tool."""

from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.seed_rates import READ
from glyphh_server.models import MachineMonth, Org, Rrotor
from glyphh_server.ops import tend
from tests.connector import granted, tool
from tests.db.helpers import Person, member, person
from tests.link import hosted_runtime, local_runtime, self_runtime


def metered_from() -> datetime:
    """An instant the meter's ticks from here, ten hours of them, stay within this month, Fly's rates in force and
    no later than now: eleven hours ago, else the month's start, else the day the rates were read."""
    now = datetime.now(UTC)
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(now - timedelta(hours=11), first, datetime.combine(READ, time(), UTC))


def micros(usd_per_month: str, seconds: int, factor: str = "1") -> int:
    """A minute's micro-dollars of this much a month (every item summed first, as the meter does)."""
    usd = Decimal(usd_per_month) * seconds / 2_592_000 * Decimal(factor) * 1_000_000
    return int(usd.to_integral_value(ROUND_HALF_EVEN))


async def _machine(engine: AsyncEngine, who: Person, name: str, size: str, state: str, **values: Any) -> Any:
    """A hosted machine, metered up to the month's start."""
    rt = await hosted_runtime(engine, who, name, size)
    values.setdefault("metered_at", metered_from())
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(state=state, **values))
    return rt


async def _months(engine: AsyncEngine, *ids: Any) -> list[tuple[int, int]]:
    async with engine.connect() as conn:
        rows = {
            r.rrotor_id: (r.cost_micros, r.charge_micros)
            for r in await conn.execute(select(MachineMonth).where(MachineMonth.rrotor_id.in_(ids)))
        }
    return [rows.get(i, (0, 0)) for i in ids]


async def test_each_minute_meters_started_seconds_and_the_volume_always_with_the_markup(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    pro, deal, free = await person(engine, "Pro"), await person(engine, "Enterprise"), await person(engine)
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == deal.org_id).values(markup_pct=25))
    small = await _machine(engine, pro, "small", "small", "online")
    medium = await _machine(engine, pro, "medium", "medium", "stopped", region="iad")
    theirs = await _machine(engine, deal, "big", "large", "online")
    at_cost = await _machine(engine, free, "left", "small", "stopped")  # held on Free: its disk's cost, no charge
    lost = await _machine(engine, pro, "lost", "small", "online", region="nowhere")
    start = metered_from()
    await tend.tally(engine, "iad", start + timedelta(seconds=60.4))
    await tend.tally(engine, "iad", start + timedelta(seconds=120.2))  # 0.4 s carried: 60 more, never 59
    await tend.tally(engine, "iad", start + timedelta(seconds=120.9))  # under a second since: nothing yet
    run = "7.15"  # small's $6.70 started, and its 3 GB at $0.15 always
    assert await _months(engine, small.id, medium.id, theirs.id, at_cost.id, lost.id) == [
        (2 * micros(run, 60), 2 * micros(run, 60, "1.3")),
        (2 * micros("1.50", 60), 2 * micros("1.50", 60, "1.3")),  # medium stopped: its 10 GB only
        (2 * micros("93.00", 60), 2 * micros("93.00", 60, "1.25")),  # large and 20 GB, the org's own markup
        (2 * micros("0.45", 60), 0),
        (0, 0),
    ]
    assert "no fly rates: machine not metered" in caplog.text


async def test_usage_is_the_orgs_precedents_and_hosting_month_to_date(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    bob = await member(engine, ada.org_id)
    await _machine(engine, ada, "research", "medium", "online", precedents=1_200)
    b = await _machine(engine, bob, "crm", "small", "stopped", precedents=300)
    away = await self_runtime(engine, ada)
    local = await local_runtime(engine, ada)
    async with engine.begin() as conn:  # per node: the fullest hosted or self-hosted runtime; a local one is not one
        for rt, held in ((away, 900), (local, 10**6)):
            await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(precedents=held))
    empty = (await client.get("/v1/billing", headers=ada.headers)).json()
    assert empty["precedents"] == {"used": 1_200, "limit": 50_000} and empty["hosting"]["machines"] == []
    for hour in range(1, 11):  # ten hours, an hour at a time
        await tend.tally(engine, "iad", metered_from() + timedelta(hours=hour))
    async with engine.begin() as conn:
        await conn.execute(delete(Rrotor).where(Rrotor.id == b.id))  # deleted: its days still billed
    billing = (await client.get("/v1/billing", headers=ada.headers)).json()
    assert (billing["plan"]["name"], billing["billing_status"], billing["renews_at"]) == ("Pro", "none", None)
    cents = {m["name"]: m["cents"] for m in billing["hosting"]["machines"]}
    assert [m["name"] for m in billing["hosting"]["machines"]] == ["crm", "research"]
    assert cents == {"research": 48, "crm": 0}  # 10 h: medium's $25.39 and 10 GB, all in; small's 3 GB only
    assert billing["hosting"]["month_to_date_cents"] == 49  # the sum first, then to the cent
    assert billing["precedents"] == {"used": 1_200, "limit": 50_000}
    me = (await client.get("/v1/me", headers=bob.headers)).json()
    assert (me["precedents"], me["hosting"]) == (billing["precedents"], billing["hosting"])
    _, auth = await granted(engine, ada)
    used = await tool(client, auth, "usage")
    assert used["content"][0]["text"] == (
        "Runtime nodes: 1 of 3.\nPrecedents: 1,200 on your fullest runtime, of 50000 per node.\n"
        "Licence key: none; rrotor runs as Community (Free) without one.\n"
        f"Hosting {billing['hosting']['month']} so far: $0.49.\ncrm (small): $0.00\nresearch (medium): $0.48"
    )
    assert used["structuredContent"]["hosting"] == billing["hosting"]
    assert (await client.get("/v1/billing")).status_code == 401
