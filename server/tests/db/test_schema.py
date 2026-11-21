"""The schema step: safe to run again, seeding each plan's first version, and a new version for a new price."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.schema import apply_schema
from glyphh_server.models import Plan, PlanVersion
from tests.conftest import SETTINGS


async def _versions(engine: AsyncEngine, plan: str) -> list[tuple[int, str | None]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(PlanVersion.version, PlanVersion.stripe_price_id)
            .join(Plan)
            .where(Plan.name == plan)
            .order_by(PlanVersion.version)
        )
        return [tuple(r) for r in rows]


async def test_running_again_changes_nothing(engine: AsyncEngine) -> None:
    before = {p: await _versions(engine, p) for p in ("Free", "Pro", "Team", "Enterprise")}
    await apply_schema(engine, SETTINGS)
    assert {p: await _versions(engine, p) for p in ("Free", "Pro", "Team", "Enterprise")} == before
    assert before["Free"] == before["Enterprise"] == [(1, None)]


async def test_a_new_stripe_price_is_a_new_version_and_an_old_one_is_not(engine: AsyncEngine) -> None:
    await apply_schema(engine, SETTINGS.model_copy(update={"stripe_price_pro": "price_test_pro_2026"}))
    assert (await _versions(engine, "Pro"))[-2:] == [(1, "price_test_pro"), (2, "price_test_pro_2026")]
    await apply_schema(engine, SETTINGS)
    assert len(await _versions(engine, "Pro")) == 2
    await apply_schema(engine, SETTINGS.model_copy(update={"stripe_price_pro": None}))
    assert len(await _versions(engine, "Pro")) == 2


async def test_a_plan_seeded_without_a_price_gets_one_as_a_new_version(engine: AsyncEngine) -> None:
    from sqlalchemy import delete, insert

    async with engine.begin() as conn:
        plan_id = (await conn.execute(insert(Plan).values(name="Trial", sort=9).returning(Plan.id))).scalar_one()
        await conn.execute(
            insert(PlanVersion).values(plan_id=plan_id, version=1, price_cents=0, max_machines=0, precedents=0)
        )
    from glyphh_server.db import seed

    trial = seed.PlanSeed("Trial", 0, "month", True, 0, 0, seed.Features())
    async with engine.begin() as conn:
        await seed._seed_version(conn, trial, "price_test_trial")
    assert await _versions(engine, "Trial") == [(1, None), (2, "price_test_trial")]
    async with engine.begin() as conn:
        await conn.execute(delete(PlanVersion).where(PlanVersion.plan_id == plan_id))
        await conn.execute(delete(Plan).where(Plan.id == plan_id))


async def test_new_cloud_limits_are_a_new_version_that_takes_the_price_and_the_orgs(engine: AsyncEngine) -> None:
    from sqlalchemy import delete, insert, update

    from glyphh_server.db import seed
    from glyphh_server.models import Org
    from glyphh_server.ops.plans import newest_version
    from tests.db.helpers import person

    async with engine.begin() as conn:
        plan_id = (await conn.execute(insert(Plan).values(name="Carry", sort=9).returning(Plan.id))).scalar_one()
        values = {"plan_id": plan_id, "version": 1, "price_cents": 4_900, "billing_interval": "month"}
        made = insert(PlanVersion).values(**values, stripe_price_id="price_test_carry", max_machines=2, sync=True)
        old = (await conn.execute(made.returning(PlanVersion.id))).scalar_one()
    who = await person(engine)
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == who.org_id).values(plan_version_id=old))
    cloud = seed.Cloud(1_000, 2_000, 3, True)
    carry = seed.PlanSeed("Carry", 4_900, "month", True, 2, None, seed.Features(sync=True), cloud)
    for _ in range(2):  # again: nothing more
        async with engine.begin() as conn:
            await seed._seed_version(conn, carry, None)
    assert await _versions(engine, "Carry") == [(1, None), (2, "price_test_carry")]
    async with engine.begin() as conn:
        new = await newest_version(conn, "Carry")
        assert (new.cloud_precedents, new.cloud_requests, new.cloud_rps, new.cloud_overage) == (1_000, 2_000, 3, True)
        assert (new.price_cents, new.max_machines, new.sync) == (4_900, 2, True)  # the deal as it was
        pinned = (await conn.execute(select(Org.plan_version_id).where(Org.id == who.org_id))).scalar_one()
        assert pinned == new.id
        free = (await newest_version(conn, "Free")).id
        await conn.execute(update(Org).where(Org.id == who.org_id).values(plan_version_id=free))
        await conn.execute(delete(PlanVersion).where(PlanVersion.plan_id == plan_id))
        await conn.execute(delete(Plan).where(Plan.id == plan_id))


async def test_the_schema_step_runs_as_a_module(engine: AsyncEngine) -> None:
    import asyncio
    import runpy
    import warnings

    def run() -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # the module is imported already; that's fine here
            runpy.run_module("glyphh_server.db.schema", run_name="__main__")

    await asyncio.to_thread(run)
    assert len(await _versions(engine, "Free")) == 1


async def test_the_plans_carry_their_price_limits_and_features(engine: AsyncEngine) -> None:
    columns = (PlanVersion.price_cents, PlanVersion.max_machines, PlanVersion.precedents, PlanVersion.offline)
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Plan.name, *columns).join(Plan).where(PlanVersion.version == 1, Plan.active).order_by(Plan.sort)
        )
        assert [tuple(r) for r in rows] == [
            ("Free", 0, 1, 5_000, False),
            ("Basic", 2_000, 1, 5_000, False),
            ("Pro", 9_900, 3, 50_000, False),
            ("Team", 29_900, 10, 500_000, False),
            ("Enterprise", None, None, None, True),
        ]


async def test_the_plans_carry_ada_clouds_limits_per_org_never_per_seat(engine: AsyncEngine) -> None:
    cloud = (PlanVersion.cloud_precedents, PlanVersion.cloud_requests, PlanVersion.cloud_rps, PlanVersion.cloud_overage)
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Plan.name, *cloud).join(Plan).where(PlanVersion.version == 1, Plan.active).order_by(Plan.sort)
        )
        assert [tuple(r) for r in rows] == [
            ("Free", 1_000, 5_000, 5, False),
            ("Basic", 10_000, 50_000, 10, True),
            ("Pro", 100_000, 1_000_000, 50, True),
            ("Team", 1_000_000, 5_000_000, 200, True),
            ("Enterprise", None, None, None, False),  # by contract
        ]
