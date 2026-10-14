"""The mods and plans every Glyphh database starts with, each plan with its first version. A Stripe price set for a
plan that its newest version doesn't sell on becomes a new version (Stripe prices never change, and neither do
versions)."""

from dataclasses import dataclass

from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import Mod, Plan, PlanVersion


@dataclass(frozen=True, slots=True)
class ModSeed:
    slug: str
    name: str
    description: str
    free: bool


MODS: tuple[ModSeed, ...] = (
    ModSeed(
        "glyphh",
        "Glyphh",
        "The account: sign in, license, account, org, plan and billing panels, and the browser machine every other "
        "mod uses",
        True,
    ),
    ModSeed(
        "glyphh-workspaces",
        "Glyphh Workspaces",
        "Workspaces: a layout grid of live web tabs plus the Claude session it runs; switching workspaces switches "
        "all of it",
        True,
    ),
    ModSeed(
        "glyphh-rpa",
        "Glyphh RPA",
        "A website as tools: commands and sequences on a site, a live tab in a panel in Claude, take control, record "
        "a task once and run it",
        False,
    ),
)


@dataclass(frozen=True, slots=True)
class PlanSeed:
    name: str
    seat_price_cents: int
    max_members: int | None
    max_installs: int | None
    max_workspaces: int | None
    all_mods: bool


FREE: str = "Free"
PLANS: tuple[PlanSeed, ...] = (
    PlanSeed(FREE, 0, 1, 1, 2, False),
    PlanSeed("Pro", 800, 1, 5, 10, True),
    PlanSeed("Team", 1_600, None, 10, None, True),
)


def stripe_prices(settings: Settings) -> dict[str, str | None]:
    """Which Stripe price each paid plan sells on: per environment, so read from settings."""
    return {FREE: None, "Pro": settings.stripe_price_pro, "Team": settings.stripe_price_team}


async def seed_mods(conn: AsyncConnection) -> None:
    for sort, seed in enumerate(MODS):
        values = {"slug": seed.slug, "name": seed.name, "description": seed.description, "free": seed.free}
        await conn.execute(upsert(Mod).values(**values, sort=sort).on_conflict_do_nothing(index_elements=[Mod.slug]))


async def seed_plans(conn: AsyncConnection, settings: Settings) -> None:
    prices = stripe_prices(settings)
    for sort, seed in enumerate(PLANS):
        await conn.execute(
            upsert(Plan).values(name=seed.name, sort=sort).on_conflict_do_nothing(index_elements=[Plan.name])
        )
        await _seed_version(conn, seed, prices[seed.name])


async def _seed_version(conn: AsyncConnection, seed: PlanSeed, price: str | None) -> None:
    plan_id = (await conn.execute(select(Plan.id).where(Plan.name == seed.name))).scalar_one()
    newest = (
        await conn.execute(
            select(PlanVersion.version, PlanVersion.stripe_price_id)
            .where(PlanVersion.plan_id == plan_id)
            .order_by(PlanVersion.version.desc())
            .limit(1)
        )
    ).first()
    if newest is not None and (price is None or newest.stripe_price_id == price):
        return
    sold = select(func.count()).where(PlanVersion.stripe_price_id == price)
    if price is not None and (await conn.execute(sold)).scalar_one():
        return
    await conn.execute(
        insert(PlanVersion).values(
            plan_id=plan_id,
            version=1 if newest is None else newest.version + 1,
            stripe_price_id=price,
            seat_price_cents=seed.seat_price_cents,
            max_members=seed.max_members,
            max_installs=seed.max_installs,
            max_workspaces=seed.max_workspaces,
            all_mods=seed.all_mods,
        )
    )
