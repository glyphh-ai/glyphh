"""The mods and plans every Glyphh database starts with, each plan with its first version, in PLANS'
order (a plan added between two takes its place at the next boot). A Stripe price set for a
plan that its newest version doesn't sell on becomes a new version (Stripe prices never change, and neither do
versions). A change of only a plan's Ada Cloud limits becomes a new version too, at the same price: it takes over the
version before it's Stripe price and its orgs, so every org on the plan has the limits. A mod no longer seeded is
retired, never deleted. Every plan includes every active mod: Ada is in all of them."""

from dataclasses import asdict, dataclass

from sqlalchemy import Row, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import Mod, Org, Plan, PlanVersion


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
class Cloud:
    """Ada Cloud's limits (docs/specs/ada-cloud.md, section 7), the org's: precedents across its models, reads a
    calendar month, calls a second; whether reads past the month are metered (else refused until it turns). None:
    unlimited, or set in the contract."""

    cloud_precedents: int | None = None
    cloud_requests: int | None = None
    cloud_rps: int | None = None
    cloud_overage: bool = False


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
    cloud: Cloud = Cloud()


FREE: str = "Free"
BASIC: str = "Basic"
ENTERPRISE: str = "Enterprise"
SALES: str = "sales@glyphh.ai"


# Never per seat, per model or per install: a plan sells runtime nodes (max_machines: Free 1, Pro 3, Team 10, Enterprise
# unlimited; Chris, 2026-10-19), precedents and sync. `precedents` is per node, across all the node's Ada models:
# the licence key's max_precedents (Free 5,000, Pro 50,000, Team 500,000, Enterprise unlimited; rrotor's
# docs/specs/licensing.md). It was the managed bucket (Pro 100,000, Team 1,000,000), what the hosted runtimes held
# together. `sync` is the key's cluster_sync_enabled. Enterprise is by contract, its price and its markup each
# customer's own (the org's markup_pct, ops/enterprise.py). TBD (Chris): Team's 500,000 precedents, and the markups
# on Fly's rates, are placeholders until set.
# Ada Cloud (Chris, 2026-10-21, decision 3): precedents per org and reads a month, never seats, models or keys: Free
# 1,000 and 5,000 (refused past them; lowered from 5,000 and 10,000 by Chris, 2026-10-22), Pro 100,000 and
# 1,000,000, Team 1,000,000 and 5,000,000 (each read past the month $1 per 10,000, metered); calls a second 5, 50,
# 200; Enterprise by contract. Team's million is not to be sold before the HNSW build memory is decided
# (docs/specs/ada-cloud.md, 10.1). Lowering a cap moves every org on the plan to the new version at the next boot
# (_carry); an org already past it keeps its precedents, and only new ones are refused (glyphh_ada/writes.py).
# Basic (Chris, 2026-10-22), between Free and Pro: $20 a month for Ada Cloud, 10,000 precedents and 50,000 reads a
# month, 10 calls a second, reads past the month metered like Pro's and Team's. No sync, HA, offline or SSO, and no
# licence key (rrotor's tiers are free, pro, team and enterprise): a self-hosted node runs as on Free, one node and
# 5,000 precedents; no hosting (no markup).
PLANS: tuple[PlanSeed, ...] = (
    PlanSeed(FREE, 0, None, True, 1, 5_000, Features(), None, Cloud(1_000, 5_000, 5)),
    PlanSeed(BASIC, 2_000, "month", True, 1, 5_000, Features(), None, Cloud(10_000, 50_000, 10, True)),
    PlanSeed("Pro", 9_900, "month", True, 3, 50_000, Features(sync=True), 30, Cloud(100_000, 1_000_000, 50, True)),
    PlanSeed(  # TBD: 500,000
        "Team", 29_900, "month", True, 10, 500_000, Features(sync=True), 30, Cloud(1_000_000, 5_000_000, 200, True)
    ),
    PlanSeed(ENTERPRISE, None, "year", False, None, None, Features(True, True, True, True), None),
)


def stripe_prices(settings: Settings) -> dict[str, str | None]:
    """Which Stripe price each self-serve paid plan sells on: per environment, so read from settings."""
    return {
        FREE: None,
        BASIC: settings.stripe_price_basic,
        "Pro": settings.stripe_price_pro,
        "Team": settings.stripe_price_team,
        ENTERPRISE: None,
    }


async def seed_mods(conn: AsyncConnection) -> None:
    for sort, seed in enumerate(MODS):
        values = {"slug": seed.slug, "name": seed.name, "description": seed.description}
        await conn.execute(upsert(Mod).values(**values, sort=sort).on_conflict_do_nothing(index_elements=[Mod.slug]))
    await conn.execute(update(Mod).where(Mod.slug.not_in([m.slug for m in MODS])).values(active=False))


async def seed_plans(conn: AsyncConnection, settings: Settings) -> None:
    prices = stripe_prices(settings)
    for sort, seed in enumerate(PLANS):
        await conn.execute(
            upsert(Plan)
            .values(name=seed.name, sort=sort)
            .on_conflict_do_update(index_elements=[Plan.name], set_={"sort": sort})
        )
        await _seed_version(conn, seed, prices[seed.name])


async def _seed_version(conn: AsyncConnection, seed: PlanSeed, price: str | None) -> None:
    plan_id = (await conn.execute(select(Plan.id).where(Plan.name == seed.name))).scalar_one()
    versions = PlanVersion.__table__
    newest = (
        await conn.execute(
            select(versions).where(versions.c.plan_id == plan_id).order_by(versions.c.version.desc()).limit(1)
        )
    ).first()
    if newest is not None and (price is None or newest.stripe_price_id == price):
        if any(getattr(newest, k) != v for k, v in asdict(seed.cloud).items()):
            await _carry(conn, newest, seed.cloud)
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
            **asdict(seed.cloud),
        )
    )


KEPT: tuple[str, ...] = (
    "plan_id",
    "price_cents",
    "billing_interval",
    "self_serve",
    "max_machines",
    "precedents",
    "sync",
    "ha",
    "offline",
    "sso",
    "hosting_markup_pct",
)


async def _carry(conn: AsyncConnection, before: Row, cloud: Cloud) -> None:
    """A new version that is the one before with these cloud limits: the same deal, so it takes over its Stripe price
    (a price sells one version) and its orgs."""
    await conn.execute(update(PlanVersion).where(PlanVersion.id == before.id).values(stripe_price_id=None))
    kept = {k: getattr(before, k) for k in KEPT}
    made = insert(PlanVersion).values(
        **kept, version=before.version + 1, stripe_price_id=before.stripe_price_id, **asdict(cloud)
    )
    new_id = (await conn.execute(made.returning(PlanVersion.id))).scalar_one()
    await conn.execute(update(Org).where(Org.plan_version_id == before.id).values(plan_version_id=new_id))
