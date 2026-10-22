"""Subscribing (Stripe Checkout: the plan's flat monthly price, with hosting on the metered hosting price, and with Ada
Cloud on, for a plan whose reads past its month are metered, the metered reads' price) and Stripe's own portal for the
card, invoices and cancelling. Only self-serve plans are bought here; Enterprise is by contract."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import Row, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.db.seed import SALES
from glyphh_server.errors import Conflict, Invalid, Unavailable
from glyphh_server.models import Org, User
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
    columns = (Org.id, Org.name, Org.stripe_customer_id, Org.stripe_subscription_id)
    return (await conn.execute(select(*columns).where(Org.id == org_id))).one()


def sold(version: Row) -> str:
    """The Stripe price a plan is bought on; refused for a plan that is by contract, or not sold through Stripe."""
    if not version.self_serve:
        raise Invalid(
            f"{version.name} is by contract: talk to us at {SALES}.", reason="not_self_serve", plan=version.name
        )
    if version.stripe_price_id is None:
        raise Invalid(f"{version.name} isn't sold through Stripe.", reason="not_sold", plan=version.name)
    return str(version.stripe_price_id)


def metered(settings: Settings, version: Row) -> list[dict[str, str]]:
    """The metered prices a subscription to this version carries: hosting's with hosting on; Ada Cloud's reads past
    the month with it on and the plan metering them. Unpriced on this server, E_UNAVAILABLE."""
    lines = []
    if settings.hosting:
        if not settings.stripe_price_hosting:
            raise Unavailable("Hosting isn't priced on this server.", reason="billing_off")
        lines.append({"price": settings.stripe_price_hosting})
    if settings.ada_cloud and version.cloud_overage:
        if not settings.stripe_price_ada:
            raise Unavailable("Ada Cloud's reads aren't priced on this server.", reason="billing_off")
        lines.append({"price": settings.stripe_price_ada})
    return lines


async def checkout(
    conn: AsyncConnection, who: Principal, stripe: StripeClient, settings: Settings, plan: str
) -> StripePage:
    require_admin(who)
    version = await newest_version(conn, plan)
    lines = [{"price": sold(version), "quantity": 1}, *metered(settings, version)]
    org = await billing_row(conn, who.org_id)
    if org.stripe_subscription_id is not None:
        raise Conflict("Your org is already subscribed: change plan instead.", reason="subscribed")
    customer = org.stripe_customer_id or await _customer(conn, who, stripe, org.name)
    url = await stripe.checkout(customer, lines, str(who.org_id), return_url(settings))
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
