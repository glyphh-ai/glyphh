"""Subscribing (Stripe Checkout: the plan per seat and each add-on as its own line) and Stripe's own portal for the
card, invoices and cancelling."""

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Row, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.errors import Conflict, Invalid
from glyphh_server.models import Org, User
from glyphh_server.ops import limits
from glyphh_server.ops.addons import allowed, quantity, sold_addon
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.guards import require_admin
from glyphh_server.ops.plans import newest_version

RETURN_PATH: str = "/billing/done"


class StripePage(BaseModel):
    url: str = Field(description="Stripe's page, to open in the browser pane")


def return_url(settings: Settings) -> str:
    return f"{settings.base_url}{RETURN_PATH}"


async def billing_row(conn: AsyncConnection, org_id: uuid.UUID) -> Row:
    return (
        await conn.execute(
            select(Org.id, Org.name, Org.stripe_customer_id, Org.stripe_subscription_id, Org.seats).where(
                Org.id == org_id
            )
        )
    ).one()


async def check_seats(conn: AsyncConnection, org_id: uuid.UUID, version: Row, seats: int) -> None:
    """Never fewer seats than are taken, nor more than the plan has members for."""
    taken = await limits.seats_taken(conn, org_id)
    if seats < taken:
        raise Conflict(f"{taken} seats are taken by members and open invites.", used=taken, seats=seats)
    if version.max_members is not None and seats > version.max_members:
        raise Invalid(f"{version.name} has room for {version.max_members} members.", plan=version.name)


async def lines(conn: AsyncConnection, version: Row, seats: int, addons: list[str]) -> list[dict[str, Any]]:
    """Checkout's lines: the plan's (when it is sold through Stripe) and each add-on's, each allowed on the plan."""
    sold = [await sold_addon(conn, mod) for mod in addons]
    if len({row.mod for row in sold}) != len(sold):
        raise Invalid("Name each add-on once.", reason="duplicate_addon")
    for row in sold:
        if not allowed(row, version.name):
            raise Conflict(f"{row.name} isn't sold with {version.name}.", reason="not_on_plan", mod=row.mod)
    if version.stripe_price_id is None and not sold:
        raise Invalid(f"{version.name} isn't sold through Stripe.", plan=version.name)
    plan = [{"price": version.stripe_price_id, "quantity": seats}] if version.stripe_price_id else []
    return plan + [{"price": row.stripe_price_id, "quantity": quantity(row, seats)} for row in sold]


async def checkout(
    conn: AsyncConnection,
    who: Principal,
    stripe: StripeClient,
    settings: Settings,
    plan: str,
    seats: int,
    addons: list[str] | None = None,
) -> StripePage:
    require_admin(who)
    version = await newest_version(conn, plan)
    items = await lines(conn, version, seats, addons or [])
    org = await billing_row(conn, who.org_id)
    if org.stripe_subscription_id is not None:
        raise Conflict("Your org is already subscribed: change plan or seats instead.", reason="subscribed")
    await check_seats(conn, who.org_id, version, seats)
    customer = org.stripe_customer_id or await _customer(conn, who, stripe, org.name)
    url = await stripe.checkout(customer, items, str(who.org_id), return_url(settings))
    return StripePage(url=url)


async def _customer(conn: AsyncConnection, who: Principal, stripe: StripeClient, org_name: str) -> str:
    email = (await conn.execute(select(User.email).where(User.id == who.user_id))).scalar_one()
    customer = await stripe.create_customer(email, org_name, str(who.org_id))
    await conn.execute(update(Org).where(Org.id == who.org_id).values(stripe_customer_id=customer))
    return customer


async def portal(conn: AsyncConnection, who: Principal, stripe: StripeClient, settings: Settings) -> StripePage:
    require_admin(who)
    org = await billing_row(conn, who.org_id)
    if org.stripe_customer_id is None:
        raise Conflict("Your org has no billing yet: subscribe first.", reason="no_billing")
    return StripePage(url=await stripe.portal(org.stripe_customer_id, return_url(settings)))
