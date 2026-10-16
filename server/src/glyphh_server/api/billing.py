"""Subscribing, changing plan or seats, adding or removing add-ons, Stripe's portal, and Stripe's webhook. Writes are
the admin's."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.pages import to_platform
from glyphh_server.ops.addons import AddonView
from glyphh_server.ops.billing import addons, changes, checkout, signature, webhook
from glyphh_server.ops.billing.addons import Action, AddonPreview
from glyphh_server.ops.billing.checkout import StripePage
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.org import OrgView

router = APIRouter(tags=["plans and billing"])


def stripe_client(request: Request) -> StripeClient:
    return StripeClient(request.app.state.http, request.app.state.settings.stripe_secret_key)


Stripe = Annotated[StripeClient, Depends(stripe_client)]


Mod = Annotated[str, Field(min_length=1, max_length=40)]


class CheckoutIn(BaseModel):
    plan: str = Field(min_length=1, max_length=40)
    seats: int = Field(ge=1, le=10_000)
    addons: list[Mod] = Field(default_factory=list, max_length=20, description="Mods to add on, each its own line")


class PreviewIn(BaseModel):
    mod: Mod
    action: Action


class AddonIn(BaseModel):
    mod: Mod
    proration_date: int | None = Field(default=None, description="The preview's, to be charged exactly what it said")


class PlanIn(BaseModel):
    plan: str = Field(min_length=1, max_length=40)


class SeatsIn(BaseModel):
    seats: int = Field(ge=1, le=10_000)


@router.post("/v1/billing/checkout", operation_id="startCheckout")
async def start_checkout(body: CheckoutIn, caller: Caller, conn: Conn, stripe: Stripe, request: Request) -> StripePage:
    """Stripe Checkout's address for a per-seat subscription and its add-ons, to open in the browser pane."""
    settings = request.app.state.settings
    return await checkout.checkout(conn, caller, stripe, settings, body.plan, body.seats, body.addons)


@router.post("/v1/billing/plan", operation_id="changePlan")
async def change_plan(body: PlanIn, caller: Caller, conn: Conn, stripe: Stripe) -> OrgView:
    """Change plan: the newest version of it, prorated."""
    return await changes.change_plan(conn, caller, stripe, body.plan)


@router.post("/v1/billing/seats", operation_id="changeSeats")
async def change_seats(body: SeatsIn, caller: Caller, conn: Conn, stripe: Stripe) -> OrgView:
    """Change the seats, prorated; never fewer than the members and open invites."""
    return await changes.change_seats(conn, caller, stripe, body.seats)


@router.post("/v1/billing/addons/preview", operation_id="previewAddon")
async def preview_addon(body: PreviewIn, caller: Caller, conn: Conn, stripe: Stripe) -> AddonPreview:
    """What adding or removing an add-on costs now, prorated, from Stripe's preview invoice; nothing changes."""
    return await addons.preview(conn, caller, stripe, body.mod, body.action)


@router.post("/v1/billing/addons", operation_id="addAddon")
async def add_addon(body: AddonIn, caller: Caller, conn: Conn, stripe: Stripe) -> list[AddonView]:
    """Add an add-on to the subscription, prorated."""
    return await addons.change(conn, caller, stripe, body.mod, "add", body.proration_date)


@router.delete("/v1/billing/addons/{mod}", operation_id="removeAddon")
async def remove_addon(
    mod: str, caller: Caller, conn: Conn, stripe: Stripe, proration_date: int | None = None
) -> list[AddonView]:
    """Remove an add-on from the subscription, prorated (a credit)."""
    return await addons.change(conn, caller, stripe, mod, "remove", proration_date)


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
async def billing_done(request: Request) -> Response:
    """Where Stripe's pages send the person back to: on to the platform's `/billing?done=1`."""
    return to_platform(request.app.state.settings, "/billing", done="1")
