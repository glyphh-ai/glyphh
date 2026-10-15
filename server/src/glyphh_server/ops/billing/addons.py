"""Adding or removing an add-on on a subscribed org's subscription, prorated, and previewing what that costs now
(Stripe's preview invoice, nothing changed). The admin's. The org is synced from Stripe's answer at once."""

import time
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.ops.addons import AddonView, allowed, list_addons, org_addons, quantity, sold_addon
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing.changes import apply, subscribed
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.plans import org_version

Action = Literal["add", "remove"]


class AddonPreview(BaseModel):
    mod: str
    action: Action
    prorated_cents: int = Field(description="What changes on the next invoice now, prorated; negative is a credit")
    currency: str
    monthly_cents: int = Field(description="The add-on's monthly amount for the seats now")
    proration_date: int = Field(description="Send it back when applying, to be charged exactly this")


def is_proration(line: dict[str, Any]) -> bool:
    """A proration line: marked on its parent's subscription item details (newer Stripe versions) or on itself."""
    details = (line.get("parent") or {}).get("subscription_item_details") or {}
    return bool(details.get("proration", line.get("proration", False)))


async def _target(conn: AsyncConnection, who: Principal, mod: str, action: Action) -> tuple[Row, Row, dict[str, Any]]:
    """The subscribed org, the add-on version and the item change, or the refusal."""
    org = await subscribed(conn, who)
    plan = await org_version(conn, who.org_id)
    have = {row.mod: row for row in await org_addons(conn, who.org_id)}
    slug = mod.strip().lower()
    if action == "add":
        if slug in have:
            raise Conflict(f"Your org has the {have[slug].name} add-on already.", reason="already_added", mod=slug)
        row = await sold_addon(conn, slug)
        if not allowed(row, plan.name):
            raise Conflict(f"{row.name} isn't sold with {plan.name}.", reason="not_on_plan", mod=slug, plan=plan.name)
        return org, row, {"price": row.stripe_price_id, "quantity": quantity(row, org.seats)}
    if slug not in have:
        raise NotFound("Your org doesn't have that add-on.", reason="not_added", mod=slug)
    if plan.stripe_price_id is None and len(have) == 1:
        raise Conflict("It is your subscription's last item: cancel in the billing portal.", reason="last_item")
    return org, have[slug], {"id": have[slug].stripe_item_id, "deleted": True}


async def preview(
    conn: AsyncConnection, who: Principal, stripe: StripeClient, mod: str, action: Action
) -> AddonPreview:
    org, row, item = await _target(conn, who, mod, action)
    at = int(time.time())
    invoice = await stripe.preview(org.stripe_subscription_id, [item], at)
    return AddonPreview(
        mod=row.mod,
        action=action,
        prorated_cents=sum(int(line["amount"]) for line in invoice["lines"]["data"] if is_proration(line)),
        currency=invoice["currency"],
        monthly_cents=row.price_cents * quantity(row, org.seats),
        proration_date=at,
    )


async def change(
    conn: AsyncConnection,
    who: Principal,
    stripe: StripeClient,
    mod: str,
    action: Action,
    proration_date: int | None = None,
) -> list[AddonView]:
    """Add or remove the add-on, prorated; the org's add-ons after."""
    org, _, item = await _target(conn, who, mod, action)
    await apply(conn, who, stripe, org, [item], proration_date)
    return await list_addons(conn, who.org_id)
