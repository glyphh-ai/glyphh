"""The landing dashboard: sign-ups and paid conversions by day; totals across every org; MRR and the plan mix from the
database alone. What the retired products counted (reads, models, precedents, the orgs that read) is answered 0."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.admin.dashboard import dashboard
from glyphh_server.admin.money import money
from glyphh_server.models import AdaMeterEvent, Org, Plan, PlanVersion
from glyphh_server.ops.orgs import new_person
from tests.admin.conftest import Admin
from tests.db.helpers import person, subscribed

RETIRED_DAY: dict[str, int] = {"active_orgs": 0, "reads": 0, "models_created": 0}
RETIRED_TOTALS: dict[str, int] = {"active_orgs": 0, "reads_month": 0, "models": 0, "precedents": 0}


async def _now(admin: Admin) -> dict[str, Any]:
    res = await admin.get("/dashboard", days=7)
    assert res.status_code == 200, res.text
    return res.json()  # type: ignore[no-any-return]


def _less(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {k: v - before[k] for k, v in after.items() if isinstance(v, int)}


async def test_each_day_counts_sign_ups_and_conversions(admin: Admin, engine: AsyncEngine) -> None:
    today = datetime.now(UTC).date()
    was = await _now(admin)
    paid = await person(engine, "Pro")
    await subscribed(engine, paid.org_id, f"sub_{paid.org_id.hex}", f"cus_{paid.org_id.hex}")
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == paid.org_id).values(first_paid_at=datetime.now(UTC)))
        await conn.execute(update(Org).where(Org.id == paid.org_id).values(suspended_at=datetime.now(UTC)))
    now = await _now(admin)
    assert now["days"] == 7 and now["since"] == (today - timedelta(days=6)).isoformat()
    assert len(now["series"]) == 7 and now["series"][-1]["day"] == today.isoformat()
    assert _less(now["series"][-1], was["series"][-1]) == {"new_users": 1, "new_orgs": 1, "conversions": 1} | (
        RETIRED_DAY
    )
    assert _less(now["totals"], was["totals"]) == {"users": 1, "orgs": 1, "suspended_orgs": 1} | RETIRED_TOTALS
    assert now["money"]["paying_orgs"] - was["money"]["paying_orgs"] == 1
    assert now["money"]["mrr_cents"] - was["money"]["mrr_cents"] == 9900


async def test_what_the_retired_products_counted_is_answered_zero(admin: Admin) -> None:
    now = await _now(admin)
    assert {k: now["totals"][k] for k in RETIRED_TOTALS} == RETIRED_TOTALS
    assert all({k: day[k] for k in RETIRED_DAY} == RETIRED_DAY for day in now["series"])


async def _org_of(conn: AsyncConnection) -> uuid.UUID:
    user = await new_person(conn, f"{uuid.uuid4().hex[:8]}@people.test", None)
    return (await conn.execute(select(Org.id).where(Org.admin_user_id == user))).scalar_one()


async def test_mrr_counts_a_year_over_twelve_and_a_contract_apart(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        before = await money(conn)
        name = f"Yearly {uuid.uuid4().hex[:6]}"
        retired = {"name": name, "sort": 99, "active": False}  # never offered: the other tests' plans stay as they are
        plan = (await conn.execute(insert(Plan).values(**retired).returning(Plan.id))).scalar_one()
        version = {"plan_id": plan, "version": 1, "price_cents": 12_000, "billing_interval": "year"}
        yearly = (await conn.execute(insert(PlanVersion).values(**version).returning(PlanVersion.id))).scalar_one()
        at = datetime.now(UTC)
        over = {"customer": "c", "period": at.strftime("%Y-%m"), "requests": 20_000, "at": at}
        await conn.execute(insert(AdaMeterEvent).values(org_id=await _org_of(conn), **over))
        yearly_org, trial = await _org_of(conn), await _org_of(conn)
        await conn.execute(
            update(Org).where(Org.id == yearly_org).values(plan_version_id=yearly, billing_status="active")
        )
        await conn.execute(update(Org).where(Org.id == trial).values(billing_status="trialing"))
    contract = await person(engine, "Enterprise")
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == contract.org_id).values(billing_status="past_due"))
        after = await money(conn)
    assert after.mrr_cents - before.mrr_cents == 1_000
    assert after.paying_orgs - before.paying_orgs == 2
    assert after.contract_orgs - before.contract_orgs == 1
    assert after.trialing_orgs - before.trialing_orgs == 1
    assert after.overage_cents_month - before.overage_cents_month == 200
    assert {p.plan: (p.orgs, p.paying, p.mrr_cents) for p in after.plans}[name] == (1, 1, 1_000)


async def test_the_series_ends_today_and_runs_back_the_days_asked(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        found = await dashboard(conn, 30, date(2026, 1, 31))
    assert len(found.series) == 30 and found.since == date(2026, 1, 2) and found.series[-1].day == date(2026, 1, 31)
    assert all((d.new_users, d.new_orgs, d.conversions) == (0, 0, 0) for d in found.series)  # before any test ran


async def test_the_days_asked_are_bounded(admin: Admin) -> None:
    assert (await admin.get("/dashboard", days=0)).status_code == 422
    assert (await admin.get("/dashboard", days=367)).status_code == 422
