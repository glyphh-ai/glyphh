"""The schema step: safe to run again, seeding each plan's one version on a new database and leaving a database
that has versions exactly as it is."""

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.schema import apply_schema
from glyphh_server.models import Plan, PlanVersion
from tests.conftest import SETTINGS

NAMES: tuple[str, ...] = ("Free", "Basic", "Pro", "Team", "Enterprise")


async def _versions(engine: AsyncEngine, plan: str) -> list[tuple[int, str | None]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(PlanVersion.version, PlanVersion.stripe_price_id)
            .join(Plan)
            .where(Plan.name == plan)
            .order_by(PlanVersion.version)
        )
        return [tuple(r) for r in rows]


async def test_a_new_database_has_each_plan_with_one_version_and_no_stripe_price(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        seeded = select(Plan.name).where(Plan.name.in_(NAMES)).order_by(Plan.sort)  # other tests add plans of theirs
        assert tuple((await conn.execute(seeded)).scalars()) == NAMES
    assert {p: await _versions(engine, p) for p in ("Free", "Enterprise")} == {
        "Free": [(1, None)],
        "Enterprise": [(1, None)],
    }


async def test_running_again_leaves_the_versions_a_database_has_as_they_are(engine: AsyncEngine) -> None:
    """As production's are: more than one version of a plan, each with the Stripe price it was sold on."""
    async with engine.begin() as conn:
        plan_id = (await conn.execute(select(Plan.id).where(Plan.name == "Basic"))).scalar_one()
        first = update(PlanVersion).where(PlanVersion.plan_id == plan_id, PlanVersion.version == 1)
        await conn.execute(first.values(stripe_price_id="price_schema_basic_1"))
        second = {"plan_id": plan_id, "version": 2, "price_cents": 2_500, "billing_interval": "month"}
        await conn.execute(insert(PlanVersion).values(**second, stripe_price_id="price_schema_basic_2"))
    before = {p: await _versions(engine, p) for p in NAMES}
    await apply_schema(engine, SETTINGS)
    assert {p: await _versions(engine, p) for p in NAMES} == before
    assert before["Basic"] == [(1, "price_schema_basic_1"), (2, "price_schema_basic_2")]


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


async def test_the_plans_carry_what_they_sold(engine: AsyncEngine) -> None:
    columns = (Plan.name, PlanVersion.price_cents, PlanVersion.billing_interval, PlanVersion.self_serve)
    found = select(*columns, PlanVersion.max_machines, PlanVersion.sync, PlanVersion.sso, PlanVersion.cloud_requests)
    async with engine.connect() as conn:
        first = found.join(Plan).where(PlanVersion.version == 1, Plan.name.in_(NAMES))
        rows = {r.name: tuple(r)[1:] for r in await conn.execute(first)}
    assert rows == {
        "Free": (0, None, True, 1, False, False, 5_000),
        "Basic": (2_000, "month", True, 1, False, False, 50_000),
        "Pro": (9_900, "month", True, 3, True, False, 1_000_000),
        "Team": (29_900, "month", True, 10, True, False, 5_000_000),
        "Enterprise": (None, "year", False, None, True, True, None),
    }
