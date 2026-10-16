"""Add-ons in tests: an org subscribed on the fake Stripe, the seeded add-ons' prices there, and a test add-on that is
flat, allowed on Free and on Team only, made for one test and removed after."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Addon, Mod, OrgAddon
from tests.db.helpers import Person, person, subscribed
from tests.fakes import FakeStripe

PRICES: dict[str, int] = {
    "price_test_pro": 800,
    "price_test_team": 1600,
    "price_test_programs": 400,
    "price_test_gateway": 400,
    "price_test_ada": 400,
    "price_test_confetti": 300,
}
CONFETTI: str = "confetti"


async def on_stripe(engine: AsyncEngine, stripe: FakeStripe, plan: str = "Pro", seats: int = 1) -> tuple[Person, str]:
    """An admin whose org is subscribed to this plan on the fake Stripe: the person and the subscription's id."""
    who = await person(engine, plan, seats=seats)
    sub, customer = f"sub_{who.org_id.hex}", f"cus_{who.org_id.hex}"
    if plan == "Free":
        stripe.subs[sub] = {"id": sub, "customer": customer, "status": "active", "metadata": {}, "items": {"data": []}}
    else:
        stripe.sub(sub, customer, f"price_test_{plan.lower()}", seats)
    stripe.prices.update(PRICES)
    await subscribed(engine, who.org_id, sub, customer)
    return who, sub


@asynccontextmanager
async def confetti(engine: AsyncEngine) -> AsyncIterator[None]:
    """A flat add-on sold with Team and allowed on Free, for one test."""
    async with engine.begin() as conn:
        await conn.execute(insert(Mod).values(slug=CONFETTI, name="Confetti", description="Bursts", sort=99))
        values = {
            "mod": CONFETTI,
            "version": 1,
            "stripe_price_id": "price_test_confetti",
            "price_cents": 300,
            "per_seat": False,
            "plans": ["Team"],
            "free": True,
            "limits": {"*": {"bursts": 1}, "Team": {"bursts": None}},
        }
        await conn.execute(insert(Addon).values(values))
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.execute(delete(OrgAddon).where(OrgAddon.mod == CONFETTI))
            await conn.execute(delete(Addon).where(Addon.mod == CONFETTI))
            await conn.execute(delete(Mod).where(Mod.slug == CONFETTI))


async def org_addons(engine: AsyncEngine, org_id: object) -> dict[str, tuple[str, str | None, int]]:
    """The org's add-on rows: mod to (status, item id, quantity)."""
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(OrgAddon.mod, OrgAddon.status, OrgAddon.stripe_item_id, OrgAddon.quantity).where(
                OrgAddon.org_id == org_id
            )
        )
        return {r.mod: (r.status, r.stripe_item_id, r.quantity) for r in rows}
