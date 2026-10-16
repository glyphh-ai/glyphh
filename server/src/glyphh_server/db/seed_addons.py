"""The add-ons every Glyphh database starts with: every mod, each with its first version. As with plans,
a Stripe price set for an add-on that its newest version doesn't sell on becomes a new version; a used version never
changes."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import Addon

PAID: list[str] = ["Pro", "Team"]
EVERY_PLAN: str = "*"


@dataclass(frozen=True, slots=True)
class AddonSeed:
    mod: str
    price_cents: int
    per_seat: bool
    plans: list[str]
    free: bool
    limits: dict[str, dict[str, Any]]


# TBD (Chris): every price, per_seat and every limit is a placeholder until set. None is allowed on Free.
ADDONS: tuple[AddonSeed, ...] = (
    AddonSeed(
        "ada",
        400,
        True,
        PAID,
        False,
        {EVERY_PLAN: {"models": 3, "precedents": 10_000}, "Team": {"models": None, "precedents": None}},
    ),
)


def addon_prices(settings: Settings) -> dict[str, str | None]:
    """Which Stripe price each add-on sells on: per environment, so read from settings."""
    return {
        "ada": settings.stripe_price_ada,
    }


async def seed_addons(conn: AsyncConnection, settings: Settings) -> None:
    prices = addon_prices(settings)
    for seed in ADDONS:
        await seed_addon(conn, seed, prices[seed.mod])


async def seed_addon(conn: AsyncConnection, seed: AddonSeed, price: str | None) -> None:
    newest = (
        await conn.execute(
            select(Addon.version, Addon.stripe_price_id)
            .where(Addon.mod == seed.mod)
            .order_by(Addon.version.desc())
            .limit(1)
        )
    ).first()
    if newest is not None and (price is None or newest.stripe_price_id == price):
        return
    sold = select(func.count()).where(Addon.stripe_price_id == price)
    if price is not None and (await conn.execute(sold)).scalar_one():
        return
    await conn.execute(
        insert(Addon).values(
            mod=seed.mod,
            version=1 if newest is None else newest.version + 1,
            stripe_price_id=price,
            price_cents=seed.price_cents,
            per_seat=seed.per_seat,
            plans=seed.plans,
            free=seed.free,
            limits=seed.limits,
        )
    )
