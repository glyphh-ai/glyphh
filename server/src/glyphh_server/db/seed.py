"""The mods and plans every Glyphh database starts with, each plan with its first version. A Stripe price set for a
plan that its newest version doesn't sell on becomes a new version (Stripe prices never change, and neither do
versions). A mod no longer seeded is retired, never deleted. The plans include only Workspaces; every other mod is an
add-on (db/seed_addons.py)."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import Mod, Plan, PlanVersion


@dataclass(frozen=True, slots=True)
class ModSeed:
    slug: str
    name: str
    description: str


MODS: tuple[ModSeed, ...] = (
    ModSeed(
        "workspaces",
        "Workspaces",
        "Sets up Claude for a kind of work in one command: a grid of your favourite pages and the app's panes, "
        "switched with /dip",
    ),
    ModSeed(
        "programs",
        "Programs",
        "Programs built with Claude, deployed by commit and run in rrotor, your own isolated runtime; called by Claude "
        "and by its routines",
    ),
    ModSeed(
        "gateway",
        "Gateway",
        "Your own models and keys in your rrotor, served as OpenAI- and Anthropic-compatible endpoints to your "
        "programs and mods",
    ),
    ModSeed(
        "ada",
        "Ada",
        "Ada models in your rrotor: a spec and a small program, deployed by commit, learning from their precedents",
    ),
)

ModLimits = dict[str, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class PlanSeed:
    name: str
    seat_price_cents: int
    max_members: int | None
    max_installs: int | None
    runtime_hours: int | None
    storage_cents_per_gb: int | None
    mod_limits: ModLimits


FREE: str = "Free"


def _limits(workspaces: int | None, favorites: int | None, stream: int) -> ModLimits:
    """The base subscription's one mod, Workspaces, and its limits; stream is a switch, 0 or 1."""
    return {"workspaces": {"workspaces": workspaces, "favorites": favorites, "stream": stream}}


# TBD (Chris): favorites and stream are placeholders until set; workspaces keeps the limits it had. Free has no hosted
# runtime (0 hours, no storage); Pro's and Team's hours are still to decide (null).
PLANS: tuple[PlanSeed, ...] = (
    PlanSeed(FREE, 0, 1, 1, 0, None, _limits(2, 5, 0)),
    PlanSeed("Pro", 800, 1, 5, None, 50, _limits(10, None, 1)),
    PlanSeed("Team", 1_600, None, 10, None, 50, _limits(None, None, 1)),
)


def stripe_prices(settings: Settings) -> dict[str, str | None]:
    """Which Stripe price each paid plan sells on: per environment, so read from settings."""
    return {FREE: None, "Pro": settings.stripe_price_pro, "Team": settings.stripe_price_team}


async def seed_mods(conn: AsyncConnection) -> None:
    for sort, seed in enumerate(MODS):
        values = {"slug": seed.slug, "name": seed.name, "description": seed.description}
        await conn.execute(upsert(Mod).values(**values, sort=sort).on_conflict_do_nothing(index_elements=[Mod.slug]))
    await conn.execute(update(Mod).where(Mod.slug.not_in([m.slug for m in MODS])).values(active=False))


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
            runtime_hours=seed.runtime_hours,
            storage_cents_per_gb=seed.storage_cents_per_gb,
            mod_limits=seed.mod_limits,
        )
    )
