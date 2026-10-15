"""Changing a subscribed org's plan (to the newest version of the other plan, prorated) or its seats (never fewer
than are taken; every per-seat add-on's quantity with the plan's). The org is synced from Stripe's answer at once; the
webhook keeps it true after."""

from typing import Any

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid
from glyphh_server.ops.addons import check_allowed
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing.checkout import billing_row, check_seats
from glyphh_server.ops.billing.items import Items, classify
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


async def items_now(conn: AsyncConnection, who: Principal, stripe: StripeClient, org: Row) -> Items:
    return await classify(conn, who.org_id, await stripe.subscription(org.stripe_subscription_id))


async def apply(
    conn: AsyncConnection,
    who: Principal,
    stripe: StripeClient,
    org: Row,
    items: list[dict[str, Any]],
    proration_date: int | None = None,
) -> None:
    changed = await stripe.change(org.stripe_subscription_id, items, proration_date)
    await sync_subscription(conn, who.org_id, changed)


async def change_plan(conn: AsyncConnection, who: Principal, stripe: StripeClient, plan: str) -> OrgView:
    org = await subscribed(conn, who)
    version = await newest_version(conn, plan)
    if version.stripe_price_id is None:
        raise Invalid(f"{version.name} isn't sold through Stripe: cancel in the billing portal.", plan=version.name)
    if version.id != (await org_version(conn, who.org_id)).id:
        await check_seats(conn, who.org_id, version, org.seats)
        await check_allowed(conn, who.org_id, version.name)
        found = await items_now(conn, who, stripe, org)
        # A new price resets an item's quantity to 1 unless the quantity is sent with it.
        item = {"price": version.stripe_price_id, "quantity": org.seats}
        await apply(conn, who, stripe, org, [item | ({"id": found.plan["id"]} if found.plan else {})])
    return await org_view(conn, who.org_id)


async def change_seats(conn: AsyncConnection, who: Principal, stripe: StripeClient, seats: int) -> OrgView:
    org = await subscribed(conn, who)
    await check_seats(conn, who.org_id, await org_version(conn, who.org_id), seats)
    found = await items_now(conn, who, stripe, org)
    items = [{"id": found.plan["id"], "quantity": seats}] if found.plan else []
    items += [{"id": on.item["id"], "quantity": seats} for on in found.addons.values() if on.addon.per_seat]
    await apply(conn, who, stripe, org, items)
    return await org_view(conn, who.org_id)
