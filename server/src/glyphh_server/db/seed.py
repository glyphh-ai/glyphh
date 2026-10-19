"""The mods and plans every Glyphh database starts with, each plan with its first version. A Stripe price set for a
plan that its newest version doesn't sell on becomes a new version (Stripe prices never change, and neither do
versions). A mod no longer seeded is retired, never deleted. Every plan includes every active mod: Ada is in all of
them."""

from dataclasses import asdict, dataclass

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
        "ada",
        "Ada",
        "Ada models in your rrotor: a spec and a small model, deployed by commit, learning from their precedents",
    ),
)


@dataclass(frozen=True, slots=True)
class Features:
    """What the licence lets a runtime do beyond running models: sync its precedents across instances, run highly
    available, run offline (air-gapped), sign in with SSO."""

    sync: bool = False
    ha: bool = False
    offline: bool = False
    sso: bool = False


@dataclass(frozen=True, slots=True)
class PlanSeed:
    name: str
    price_cents: int | None
    interval: str | None
    self_serve: bool
    max_machines: int | None
    precedents: int | None
    features: Features
    hosting_markup_pct: int | None


FREE: str = "Free"
ENTERPRISE: str = "Enterprise"
SALES: str = "sales@glyphh.ai"


# Never per seat, per model or per install: a plan sells runtime nodes (max_machines: Free 1, Pro 3, Team 10, Enterprise
# unlimited; Chris, 2026-10-19), precedents and sync. `precedents` is per node, across all the node's Ada models:
# the licence key's max_precedents (Free 5,000, Pro 50,000, Team 500,000, Enterprise unlimited; rrotor's
# docs/specs/licensing.md). It was the managed bucket (Pro 100,000, Team 1,000,000), what the hosted runtimes held
# together. `sync` is the key's cluster_sync_enabled. Enterprise is by contract, its price and its markup each
# customer's own (the org's markup_pct, ops/enterprise.py). TBD (Chris): Team's 500,000 precedents, and the markups
# on Fly's rates, are placeholders until set.
PLANS: tuple[PlanSeed, ...] = (
    PlanSeed(FREE, 0, None, True, 1, 5_000, Features(), None),
    PlanSeed("Pro", 9_900, "month", True, 3, 50_000, Features(sync=True), 30),
    PlanSeed("Team", 29_900, "month", True, 10, 500_000, Features(sync=True), 30),  # TBD: 500,000
    PlanSeed(ENTERPRISE, None, "year", False, None, None, Features(True, True, True, True), None),
)


def stripe_prices(settings: Settings) -> dict[str, str | None]:
    """Which Stripe price each self-serve paid plan sells on: per environment, so read from settings."""
    return {FREE: None, "Pro": settings.stripe_price_pro, "Team": settings.stripe_price_team, ENTERPRISE: None}


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
            price_cents=seed.price_cents,
            billing_interval=seed.interval,
            self_serve=seed.self_serve,
            max_machines=seed.max_machines,
            precedents=seed.precedents,
            hosting_markup_pct=seed.hosting_markup_pct,
            **asdict(seed.features),
        )
    )
