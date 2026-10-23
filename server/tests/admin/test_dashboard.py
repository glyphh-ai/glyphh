"""The landing dashboard: sign-ups, active orgs and reads, models made and paid conversions by day; totals across
every org (its Ada schema read as metadata); MRR and the plan mix from the database alone."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
from redis.asyncio import Redis
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_ada import orgschema, pg
from glyphh_ada.requests import period
from glyphh_server.admin import adascan
from glyphh_server.admin.dashboard import dashboard
from glyphh_server.admin.money import money
from glyphh_server.models import AdaMeterEvent, AdaModelDay, AdaUsage, Org, Plan, PlanVersion
from glyphh_server.ops.orgs import new_person
from tests.admin.ada import DATABASE_URL, ada_org
from tests.admin.conftest import Admin
from tests.db.helpers import person, subscribed


async def _read(engine: AsyncEngine, org: uuid.UUID, day: date, n: int, metric: str = "read:decide") -> None:
    async with engine.begin() as conn:
        await conn.execute(insert(AdaModelDay).values(org_id=org, model="m", day=day, metric=metric, n=n))


async def _now(admin: Admin, redis: Redis) -> dict[str, Any]:
    await redis.delete(adascan.SCAN_KEY)
    res = await admin.get("/dashboard", days=7)
    assert res.status_code == 200, res.text
    return res.json()  # type: ignore[no-any-return]


def _less(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {k: v - before[k] for k, v in after.items() if isinstance(v, int)}


async def test_each_day_counts_sign_ups_reads_models_and_conversions(
    admin: Admin, engine: AsyncEngine, redis: Redis
) -> None:
    today = datetime.now(UTC).date()
    was = await _now(admin, redis)
    paid = await person(engine, "Pro")
    await subscribed(engine, paid.org_id, f"sub_{paid.org_id.hex}", f"cus_{paid.org_id.hex}")
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == paid.org_id).values(first_paid_at=datetime.now(UTC)))
        await conn.execute(insert(AdaUsage).values(org_id=paid.org_id, period=period(), requests=7))
    await _read(engine, paid.org_id, today, 5)
    await _read(engine, paid.org_id, today, 3, "decided")  # an answer, not a read
    await _read(engine, paid.org_id, today - timedelta(days=1), 2)
    await _read(engine, paid.org_id, today - timedelta(days=40), 9)  # before the period
    ada_org(paid.org_id, [{"name": "loans", "precedents": 12}, {"name": "gone", "precedents": 4, "deleted": True}])
    now = await _now(admin, redis)
    assert now["days"] == 7 and now["since"] == (today - timedelta(days=6)).isoformat()
    assert now["series"][-1]["day"] == today.isoformat()
    today_less = _less(now["series"][-1], was["series"][-1])
    assert today_less == {
        "new_users": 1,
        "new_orgs": 1,
        "active_orgs": 1,
        "reads": 5,
        "models_created": 2,
        "conversions": 1,
    }
    assert _less(now["series"][-2], was["series"][-2])["reads"] == 2
    totals = _less(now["totals"], was["totals"])
    assert totals == {
        "users": 1,
        "orgs": 1,
        "suspended_orgs": 0,
        "active_orgs": 1,
        "reads_month": 7,
        "models": 1,
        "precedents": 12,
    }
    assert now["money"]["paying_orgs"] - was["money"]["paying_orgs"] == 1
    assert now["money"]["mrr_cents"] - was["money"]["mrr_cents"] == 9900


async def test_the_scan_is_kept_a_minute(engine: AsyncEngine, redis: Redis) -> None:
    await redis.delete(adascan.SCAN_KEY)
    org = await person(engine)
    ada_org(
        org.org_id,
        [{"name": "first", "precedents": 1}],
        [{"model": "first", "kind": "learn", "state": "done", "seconds": 3}],
    )
    async with engine.begin() as conn:
        first = adascan.by_org(await adascan.scan(conn, redis))[org.org_id]
    ada_org(org.org_id, [{"name": "second", "precedents": 1}])
    async with engine.begin() as conn:
        again = adascan.by_org(await adascan.scan(conn, redis))[org.org_id]
        fresh = await adascan.one(conn, org.org_id)
        none = await adascan.one(conn, uuid.uuid4())
    assert [m.name for m in first.models] == [m.name for m in again.models] == ["first"]
    assert [(j.kind, j.state, round(j.seconds or 0)) for j in again.jobs] == [("learn", "done", 3)]
    assert [m.name for m in fresh.models] == ["first", "second"] and fresh.precedents == 2
    assert none.models == [] and none.jobs == []


async def test_a_schema_before_the_kernels_counts_holds_none(engine: AsyncEngine) -> None:
    org = await person(engine)
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        orgschema.ensure(conn, str(org.org_id))
        pg.enter(conn, str(org.org_id))
        s = f'"{pg.schema_for(str(org.org_id))}"'
        model = uuid.uuid4()
        conn.execute(f"INSERT INTO {s}.models (id, name, created_by) VALUES (%s, 'early', 't')", (model,))
        conn.execute(
            f"INSERT INTO {s}.spec_versions (model_id, version, spec, made_by, store) VALUES (%s, 1, '{{}}', 't', 'x')",
            (model,),
        )
    async with engine.begin() as conn:
        found = await adascan.one(conn, org.org_id)
    assert [(m.name, m.precedents, m.ada) for m in found.models] == [("early", 0, None)]


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
        over = {"customer": "c", "period": period(), "requests": 20_000, "at": datetime.now(UTC)}
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
    assert after.contract_orgs - before.contract_orgs == 1
    assert after.trialing_orgs - before.trialing_orgs == 1
    assert after.overage_cents_month - before.overage_cents_month == 200
    assert {p.plan: p.mrr_cents for p in after.plans}[name] == 1_000


async def test_the_series_ends_today_and_runs_back_the_days_asked(engine: AsyncEngine, redis: Redis) -> None:
    async with engine.begin() as conn:
        found = await dashboard(conn, redis, 30, date(2026, 1, 31))
    assert len(found.series) == 30 and found.since == date(2026, 1, 2) and found.series[-1].day == date(2026, 1, 31)
