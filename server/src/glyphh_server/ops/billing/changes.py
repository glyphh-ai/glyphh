"""Changing a subscribed org's plan: to the newest version of another self-serve plan, prorated by Stripe; or down to
Free, which cancels the subscription now (invoiced now, prorated). An org on a plan by contract (Enterprise) changes it
with Glyphh, not here. The org is synced from Stripe's answer at once; the webhook keeps it true after."""

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.seed import FREE, SALES
from glyphh_server.errors import Conflict
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing import ada_meter
from glyphh_server.ops.billing.checkout import billing_row, sold
from glyphh_server.ops.billing.items import classify
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.billing.sync import sync_subscription
from glyphh_server.ops.guards import require_admin
from glyphh_server.ops.org import OrgView, org_view
from glyphh_server.ops.plans import newest_version, org_version


async def subscribed(conn: AsyncConnection, who: Principal) -> Row:
    """The admin's org, which must be subscribed."""
    require_admin(who)
    org = await billing_row(conn, who.org_id)
    if org.stripe_subscription_id is None:
        raise Conflict("Your org isn't subscribed: start with checkout.", reason="not_subscribed")
    return org


async def to_free(
    conn: AsyncConnection, who: Principal, stripe: StripeClient, org: Row, ada_price: str | None = None
) -> None:
    """The subscription cancelled now, once Ada Cloud's reads past the month are reported, so the last invoice carries
    them."""
    await ada_meter.report(conn.engine, stripe, ada_price, only=who.org_id)
    await sync_subscription(conn, who.org_id, await stripe.cancel(org.stripe_subscription_id))


async def change_plan(
    conn: AsyncConnection, who: Principal, stripe: StripeClient, plan: str, ada_price: str | None = None
) -> OrgView:
    """ada_price: Ada Cloud's metered reads' price (GLYPHH_STRIPE_PRICE_ADA), which a last report needs on the
    subscription."""
    org = await subscribed(conn, who)
    current = await org_version(conn, who.org_id)
    if not current.self_serve:
        raise Conflict(f"Your {current.name} plan is by contract: talk to us at {SALES}.", reason="contract")
    version = await newest_version(conn, plan)
    if version.name == FREE:
        await to_free(conn, who, stripe, org, ada_price)
        return await org_view(conn, who.org_id)
    price = sold(version)
    if version.id != current.id:
        found = await classify(conn, who.org_id, await stripe.subscription(org.stripe_subscription_id))
        item = {"price": price, "quantity": 1} | ({"id": found.plan["id"]} if found.plan else {})
        await sync_subscription(conn, who.org_id, await stripe.change(org.stripe_subscription_id, [item]))
    return await org_view(conn, who.org_id)
