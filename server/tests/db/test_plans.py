import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.schema import apply_schema
from glyphh_server.models import Plan
from tests.conftest import SETTINGS


async def _plans(engine: AsyncEngine) -> list[tuple]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Plan.name, Plan.price_cents, Plan.max_seats, Plan.stripe_price_id).order_by(Plan.sort)
        )
        return [tuple(r) for r in rows]


async def test_the_five_plans_are_seeded_with_their_seats_and_stripe_prices(engine: AsyncEngine) -> None:
    assert await _plans(engine) == [
        ("Free", 0, 1, None),
        ("Solo", 2_000, 1, "price_test_solo"),
        ("Basic", 4_000, 25, "price_test_basic"),
        ("Pro", 15_000, 100, "price_test_pro"),
        ("Enterprise", 0, None, None),
    ]


async def test_rerunning_the_seed_keeps_an_admins_edits(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(Plan).where(Plan.name == "Basic").values(max_seats=30))
    await apply_schema(engine, SETTINGS)
    seats = {name: seats for name, _, seats, _ in await _plans(engine)}
    assert seats["Basic"] == 30 and len(seats) == 5
    async with engine.begin() as conn:
        await conn.execute(update(Plan).where(Plan.name == "Basic").values(max_seats=25))


async def test_plans_are_sold_until_retired(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        assert set((await conn.execute(select(Plan.active))).scalars()) == {True}


@pytest.mark.parametrize(
    ("values", "constraint"),
    [
        ({"price_cents": -1}, "plans_price"),
        ({"max_seats": 0}, "plans_seats"),
        ({"stripe_price_id": "price_test_pro"}, "plans_stripe_price_id_key"),
        ({"name": "Free"}, "plans_name_key"),
    ],
)
async def test_a_bad_plan_is_refused(engine: AsyncEngine, values: dict, constraint: str) -> None:
    row = {"name": "Test", "price_cents": 100, **values}
    with pytest.raises(IntegrityError, match=constraint):
        async with engine.begin() as conn:
            await conn.execute(insert(Plan).values(row))
