"""Changing a subscribed org's plan (to the newest version of the other plan, prorated) or its seats (never fewer
than are taken). The org is synced from Stripe's answer at once; the webhook keeps it true after."""

from typing import Any

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing.checkout import billing_row, check_seats
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.billing.sync import sync_subscription
from glyphh_server.ops.guards import require_admin
from glyphh_server.ops.org import OrgView, org_view
from glyphh_server.ops.plans import newest_version, org_version


async def _subscribed(conn: AsyncConnection, who: Principal) -> Row:
    require_admin(who)
    org = await billing_row(conn, who.org_id)
    if org.stripe_subscription_id is None:
        raise Conflict("Your org isn't subscribed: start with checkout.", reason="not_subscribed")
    return org


async def _change(conn: AsyncConnection, who: Principal, stripe: StripeClient, org: Row, item: dict[str, Any]) -> None:
    sub = await stripe.subscription(org.stripe_subscription_id)
    changed = await stripe.change(org.stripe_subscription_id, {"id": sub["items"]["data"][0]["id"], **item})
    await sync_subscription(conn, who.org_id, changed)


async def change_plan(conn: AsyncConnection, who: Principal, stripe: StripeClient, plan: str) -> OrgView:
    org = await _subscribed(conn, who)
    version = await newest_version(conn, plan)
    if version.stripe_price_id is None:
        raise Invalid(f"{version.name} isn't sold through Stripe: cancel in the billing portal.", plan=version.name)
    if version.id != (await org_version(conn, who.org_id)).id:
        await check_seats(conn, who.org_id, version, org.seats)
        await _change(conn, who, stripe, org, {"price": version.stripe_price_id})
    return await org_view(conn, who.org_id)


async def change_seats(conn: AsyncConnection, who: Principal, stripe: StripeClient, seats: int) -> OrgView:
    org = await _subscribed(conn, who)
    await check_seats(conn, who.org_id, await org_version(conn, who.org_id), seats)
    await _change(conn, who, stripe, org, {"quantity": seats})
    return await org_view(conn, who.org_id)
