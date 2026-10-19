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

    trial = seed.PlanSeed("Trial", 0, "month", True, 0, 0, seed.Features(), None)
    async with engine.begin() as conn:
        await seed._seed_version(conn, trial, "price_test_trial")
    assert await _versions(engine, "Trial") == [(1, None), (2, "price_test_trial")]
    async with engine.begin() as conn:
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


async def test_the_plans_carry_their_price_limits_features_and_hidden_markup(engine: AsyncEngine) -> None:
    columns = (PlanVersion.price_cents, PlanVersion.max_machines, PlanVersion.precedents, PlanVersion.offline)
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Plan.name, *columns, PlanVersion.hosting_markup_pct)
            .join(Plan)
            .where(PlanVersion.version == 1)
            .order_by(Plan.sort)
        )
        assert [tuple(r) for r in rows] == [
            ("Free", 0, 1, 0, False, None),
            ("Pro", 9_900, 3, 100_000, False, 30),
            ("Team", 29_900, 10, 1_000_000, False, 30),
            ("Enterprise", None, None, None, True, None),
        ]
