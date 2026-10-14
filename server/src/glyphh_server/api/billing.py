"""Subscribing, changing plan or seats, Stripe's portal, and Stripe's webhook. Writes are the admin's."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.pages import page
from glyphh_server.ops.billing import changes, checkout, signature, webhook
from glyphh_server.ops.billing.checkout import StripePage
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.org import OrgView

router = APIRouter(tags=["plans and billing"])


def stripe_client(request: Request) -> StripeClient:
    return StripeClient(request.app.state.http, request.app.state.settings.stripe_secret_key)


Stripe = Annotated[StripeClient, Depends(stripe_client)]


class CheckoutIn(BaseModel):
    plan: str = Field(min_length=1, max_length=40)
    seats: int = Field(ge=1, le=10_000)


class PlanIn(BaseModel):
    plan: str = Field(min_length=1, max_length=40)


class SeatsIn(BaseModel):
    seats: int = Field(ge=1, le=10_000)


@router.post("/v1/billing/checkout", operation_id="startCheckout")
async def start_checkout(body: CheckoutIn, caller: Caller, conn: Conn, stripe: Stripe, request: Request) -> StripePage:
    """Stripe Checkout's address for a per-seat subscription, to open in the browser pane."""
    return await checkout.checkout(conn, caller, stripe, request.app.state.settings, body.plan, body.seats)


@router.post("/v1/billing/plan", operation_id="changePlan")
async def change_plan(body: PlanIn, caller: Caller, conn: Conn, stripe: Stripe) -> OrgView:
    """Change plan: the newest version of it, prorated."""
    return await changes.change_plan(conn, caller, stripe, body.plan)


@router.post("/v1/billing/seats", operation_id="changeSeats")
async def change_seats(body: SeatsIn, caller: Caller, conn: Conn, stripe: Stripe) -> OrgView:
    """Change the seats, prorated; never fewer than the members and open invites."""
    return await changes.change_seats(conn, caller, stripe, body.seats)


@router.post("/v1/billing/portal", operation_id="openBillingPortal")
async def open_portal(caller: Caller, conn: Conn, stripe: Stripe, request: Request) -> StripePage:
    """Stripe's portal address: card, invoices, cancel."""
    return await checkout.portal(conn, caller, stripe, request.app.state.settings)


@router.post("/v1/stripe/webhook", operation_id="stripeWebhook", status_code=204)
async def stripe_webhook(
    request: Request, conn: Conn, stripe_signature: Annotated[str | None, Header()] = None
) -> Response:
    """Stripe's events keep orgs true: plan version, seats, status. Signed by Stripe, or refused."""
    secret = request.app.state.settings.stripe_webhook_secret
    event = signature.verified_event(secret, await request.body(), stripe_signature)
    await webhook.handle_event(conn, stripe_client(request), event)
    return Response(status_code=204)


@router.get(checkout.RETURN_PATH, include_in_schema=False)
async def billing_done() -> Response:
    """Where Stripe's pages send the person back to."""
    return page("Billing", "Done. Go back to Claude.")
