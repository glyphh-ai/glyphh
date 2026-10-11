"""The rows every Glyphh database starts with: the plans, and Glyphh, the parent org."""

from dataclasses import asdict, dataclass

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import Plan

PARENT_ORG: str = "Glyphh"
PARENT_PLAN: str = "Enterprise"


@dataclass(frozen=True, slots=True)
class PlanSeed:
    name: str
    price_cents: int
    max_seats: int | None
    rpm_limit: int | None
    tpm_limit: int | None


PLANS: tuple[PlanSeed, ...] = (
    PlanSeed("Free", 0, 1, 60, 50_000),
    PlanSeed("Solo", 2_000, 1, 200, 200_000),
    PlanSeed("Basic", 4_000, 25, 600, 500_000),
    PlanSeed("Pro", 15_000, 100, 2_000, 2_000_000),
    PlanSeed("Enterprise", 0, None, None, None),
)


def stripe_prices(settings: Settings) -> dict[str, str | None]:
    """Which Stripe price each paid plan sells on: per environment, so read from settings."""
    return {"Solo": settings.stripe_price_solo, "Basic": settings.stripe_price_basic, "Pro": settings.stripe_price_pro}


async def seed_plans(conn: AsyncConnection, settings: Settings) -> None:
    prices = stripe_prices(settings)
    rows = [{**asdict(p), "stripe_price_id": prices.get(p.name), "sort": i} for i, p in enumerate(PLANS)]
    await conn.execute(insert(Plan).values(rows).on_conflict_do_nothing(index_elements=[Plan.name]))


async def seed_parent_org(conn: AsyncConnection) -> None:
    plan_id = (await conn.execute(select(Plan.id).where(Plan.name == PARENT_PLAN))).scalar_one()
    await conn.execute(
        text(
            "INSERT INTO orgs (name, plan_id) VALUES (:name, :plan_id)"
            " ON CONFLICT ((true)) WHERE parent_id IS NULL DO NOTHING"
        ),
        {"name": PARENT_ORG, "plan_id": plan_id},
    )
