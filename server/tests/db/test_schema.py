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
    before = {p: await _versions(engine, p) for p in ("Free", "Pro", "Team")}
    await apply_schema(engine, SETTINGS)
    assert {p: await _versions(engine, p) for p in ("Free", "Pro", "Team")} == before
    assert before["Free"] == [(1, None)]


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
            insert(PlanVersion).values(
                plan_id=plan_id,
                version=1,
                seat_price_cents=0,
                max_members=1,
                max_installs=1,
            )
        )
    from glyphh_server.db import seed

    trial = seed.PlanSeed("Trial", 0, 1, 1, 0, None, {})
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


async def test_the_plans_carry_their_hosted_runtime_hours_and_storage_rate(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Plan.name, PlanVersion.runtime_hours, PlanVersion.storage_cents_per_gb)
            .join(Plan)
            .where(PlanVersion.version == 1)
            .order_by(Plan.sort)
        )
        assert [tuple(r) for r in rows] == [("Free", 5, None), ("Pro", 50, 50), ("Team", 50, 50)]


async def test_an_addons_new_stripe_price_is_a_new_version_and_an_org_keeps_the_one_it_added(
    engine: AsyncEngine,
) -> None:
    from sqlalchemy import delete

    from glyphh_server.db import seed_addons
    from glyphh_server.models import Addon, OrgAddon
    from glyphh_server.ops.addons import list_addons, newest_addons
    from tests.db.helpers import person, with_addon

    ada = await person(engine, "Pro")
    await with_addon(engine, ada.org_id, "ada")
    try:
        await apply_schema(engine, SETTINGS.model_copy(update={"stripe_price_ada": "price_test_ada_2026"}))
        await apply_schema(engine, SETTINGS.model_copy(update={"stripe_price_ada": None}))
        async with engine.begin() as conn:
            (seed,) = [s for s in seed_addons.ADDONS if s.mod == "ada"]
            await seed_addons.seed_addon(conn, seed, "price_test_ada")
            versions = await conn.execute(select(Addon.version, Addon.stripe_price_id).where(Addon.mod == "ada"))
            assert sorted(tuple(v) for v in versions) == [(1, "price_test_ada"), (2, "price_test_ada_2026")]
            assert next(r for r in await newest_addons(conn) if r.mod == "ada").version == 2
            mine = next(a for a in await list_addons(conn, ada.org_id) if a.mod == "ada")
            assert (mine.version, mine.added) == (1, True)
    finally:
        async with engine.begin() as conn:
            await conn.execute(delete(OrgAddon).where(OrgAddon.org_id == ada.org_id))
            await conn.execute(delete(Addon).where(Addon.mod == "ada", Addon.version == 2))
