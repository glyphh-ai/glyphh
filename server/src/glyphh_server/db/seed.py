"""The plans every Glyphh database starts with, each plan with its first version, in PLANS'
order (a plan added between two takes its place at the next boot). A Stripe price set for a
plan that its newest version doesn't sell on becomes a new version (Stripe prices never change, and neither do
versions). A change of only a plan's Ada Cloud limits or token allowance becomes a new version too, at the same
price: it takes over the version before it's Stripe price and its orgs, so every org on the plan has the limits."""

from dataclasses import asdict, dataclass

from sqlalchemy import Row, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import Org, Plan, PlanVersion


@dataclass(frozen=True, slots=True)
class Features:
    """A plan version's feature columns. Only `sso` (single sign-on) is read; sync, ha and offline were rrotor's and
    stay until their columns are dropped."""

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
    cloud: Cloud = Cloud()
    llm_tokens: int | None = None  # Glyphh-hosted models' tokens a month (docs/specs/tokens.md); None: by contract

    def carried(self) -> dict[str, int | bool | None]:
        """What a version changing only these keeps the price and orgs of the one before for (_carry)."""
        return {**asdict(self.cloud), "llm_tokens": self.llm_tokens}


FREE: str = "Free"
BASIC: str = "Basic"
ENTERPRISE: str = "Enterprise"
SALES: str = "sales@glyphh.ai"


# Never per seat, per model or per install. `max_machines`, `precedents` and the sync, ha and offline features were
# rrotor's (runtime nodes, precedents per node): nothing reads them, and they stay as they were seeded until their
# columns are dropped. Enterprise is by contract, its price each customer's own (ops/enterprise.py).
# Ada Cloud (Chris, 2026-10-21, decision 3): precedents per org and reads a month, never seats, models or keys: Free
# 1,000 and 5,000 (refused past them; lowered from 5,000 and 10,000 by Chris, 2026-10-22), Pro 100,000 and
# 1,000,000, Team 1,000,000 and 5,000,000 (each read past the month $1 per 10,000, metered); calls a second 5, 50,
# 200; Enterprise by contract. Team's million is not to be sold before the HNSW build memory is decided
# (docs/specs/ada-cloud.md, 10.1). Lowering a cap moves every org on the plan to the new version at the next boot
# (_carry); an org already past it keeps its precedents, and only new ones are refused (glyphh_ada/writes.py).
# Basic (Chris, 2026-10-22), between Free and Pro: $20 a month for Ada Cloud, 10,000 precedents and 50,000 reads a
# month, 10 calls a second, reads past the month metered like Pro's and Team's. No SSO.
# Glyphh-hosted models (Chris, 2026-11-10, docs/specs/tokens.md): tokens a calendar month, then charged in dollars to a
# prepaid balance (Free may buy one too): Free 250,000, Basic 5,000,000, Pro 25,000,000, Team 100,000,000, Enterprise
# by contract. TBD (Chris): every allowance is a placeholder until set.
PLANS: tuple[PlanSeed, ...] = (
    PlanSeed(FREE, 0, None, True, 1, 5_000, Features(), Cloud(1_000, 5_000, 5), 250_000),
    PlanSeed(BASIC, 2_000, "month", True, 1, 5_000, Features(), Cloud(10_000, 50_000, 10, True), 5_000_000),
    PlanSeed(
        "Pro", 9_900, "month", True, 3, 50_000, Features(sync=True), Cloud(100_000, 1_000_000, 50, True), 25_000_000
    ),
    PlanSeed(  # TBD: 500,000
        "Team", 29_900, "month", True, 10, 500_000, Features(True), Cloud(1_000_000, 5_000_000, 200, True), 100_000_000
    ),
    PlanSeed(ENTERPRISE, None, "year", False, None, None, Features(True, True, True, True)),
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
        if any(getattr(newest, k) != v for k, v in seed.carried().items()):
            await _carry(conn, newest, seed.carried())
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
            **asdict(seed.features),
            **seed.carried(),
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
)


async def _carry(conn: AsyncConnection, before: Row, carried: dict[str, int | bool | None]) -> None:
    """A new version that is the one before with these cloud limits and token allowance: the same deal, so it takes
    over its Stripe price (a price sells one version) and its orgs."""
    await conn.execute(update(PlanVersion).where(PlanVersion.id == before.id).values(stripe_price_id=None))
    kept = {k: getattr(before, k) for k in KEPT}
    made = insert(PlanVersion).values(
        **kept, version=before.version + 1, stripe_price_id=before.stripe_price_id, **carried
    )
    new_id = (await conn.execute(made.returning(PlanVersion.id))).scalar_one()
    await conn.execute(update(Org).where(Org.plan_version_id == before.id).values(plan_version_id=new_id))
