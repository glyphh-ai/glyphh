"""The card on file and the invoices, read from Stripe for the platform's Billing (GET /v1/billing/payment), and the
way to add or replace the card (POST /v1/billing/card: Stripe's portal, opened at its payment-method page, the org's
Stripe customer made first if it has none). Nothing of the card is kept here: its brand, last four digits and expiry
are Stripe's, read each time. The admin's."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.billing.checkout import StripePage, _customer, billing_row, return_url
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.guards import require_admin

INVOICES: int = 12


class Card(BaseModel):
    brand: str = Field(description="visa, mastercard, amex, ...")
    last4: str
    exp_month: int
    exp_year: int


class Invoice(BaseModel):
    id: str
    number: str | None
    status: str = Field(description="draft, open, paid, uncollectible or void")
    total_cents: int
    currency: str
    created: datetime
    url: str | None = Field(description="Stripe's page for it")
    pdf: str | None


class Payment(BaseModel):
    card: Card | None = Field(description="null: no card on file")
    invoices: list[Invoice] = Field(description="Newest first, the last twelve")


def _invoice(found: dict[str, Any]) -> Invoice:
    return Invoice(
        id=found["id"],
        number=found.get("number"),
        status=found.get("status") or "draft",
        total_cents=int(found.get("total") or 0),
        currency=found.get("currency") or "usd",
        created=datetime.fromtimestamp(int(found["created"]), UTC),
        url=found.get("hosted_invoice_url"),
        pdf=found.get("invoice_pdf"),
    )


async def payment(conn: AsyncConnection, who: Principal, stripe: Callable[[], StripeClient]) -> Payment:
    """Stripe is asked only for an org that has a customer there: one that never paid has neither card nor invoice."""
    require_admin(who)
    customer = (await billing_row(conn, who.org_id)).stripe_customer_id
    if customer is None:
        return Payment(card=None, invoices=[])
    client = stripe()
    card = await client.default_card(customer)
    shown = None if card is None else Card(**{k: card[k] for k in ("brand", "last4", "exp_month", "exp_year")})
    return Payment(card=shown, invoices=[_invoice(i) for i in await client.invoices(customer, INVOICES)])


async def card(conn: AsyncConnection, who: Principal, stripe: StripeClient, settings: Settings) -> StripePage:
    require_admin(who)
    org = await billing_row(conn, who.org_id)
    customer = org.stripe_customer_id or await _customer(conn, who, stripe, org.name)
    return StripePage(url=await stripe.portal(customer, return_url(settings), flow="payment_method_update"))
