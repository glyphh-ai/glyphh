"""Topping up the overage balance the bots and the Glyphh-hosted models draw on past the plan's tokens (tokens.md): the
admin's, in dollars, $10 to $1,000, through Stripe Checkout as one payment, priced in the session itself. The balance
is credited only when Stripe's webhook says the session completed and was paid, once per session however often it
is sent; Stripe's page then sends the person back to the platform's Billing with `?topup=1`."""

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.llm import ledger
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing.checkout import StripePage, _customer, billing_row
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.guards import require_admin

log = logging.getLogger("glyphh.billing")

MIN_CENTS: int = 1_000
MAX_CENTS: int = 100_000
PRESETS_CENTS: tuple[int, ...] = (1_000, 2_500, 5_000, 10_000)
KIND: str = "llm_topup"  # the session's metadata kind
PAID_EVENTS: frozenset[str] = frozenset({"checkout.session.completed", "checkout.session.async_payment_succeeded"})


class TopupIn(BaseModel):
    amount_cents: int = Field(
        ge=MIN_CENTS, le=MAX_CENTS, description="US cents to add: $10 to $1,000 (presets $10, $25, $50, $100)"
    )


def line(amount_cents: int) -> dict[str, Any]:
    product = {"name": "Glyphh balance (bots and hosted models)"}
    price = {"currency": "usd", "unit_amount": amount_cents, "product_data": product}
    return {"price_data": price, "quantity": 1}


async def topup(
    conn: AsyncConnection, who: Principal, stripe: StripeClient, settings: Settings, amount_cents: int
) -> StripePage:
    require_admin(who)
    org = await billing_row(conn, who.org_id)
    customer = org.stripe_customer_id or await _customer(conn, who, stripe, org.name)
    back = f"{settings.platform_base}/settings/billing"
    url = await stripe.pay(customer, line(amount_cents), str(who.org_id), f"{back}?topup=1", back)
    return StripePage(url=url)


def paid(obj: dict[str, Any]) -> bool:
    """A top-up's session, paid in dollars."""
    ours = (obj.get("metadata") or {}).get("kind") == KIND
    return ours and obj.get("payment_status") == "paid" and obj.get("currency") == "usd"


async def credited(conn: AsyncConnection, org_id: uuid.UUID | None, obj: dict[str, Any]) -> bool:
    """A paid top-up's amount added to the org's balance, once for its session; answers whether it was now."""
    if org_id is None or not paid(obj):
        log.info("checkout payment not credited", extra=fields(session=obj.get("id"), status=obj.get("payment_status")))
        return False
    micros = int(obj["amount_total"]) * ledger.MICROS_PER_CENT
    return await ledger.credit(conn, org_id, "topup", micros, stripe_ref=str(obj["id"]))
