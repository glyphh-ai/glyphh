"""The org's billing and use; subscribing, changing plan, Stripe's portal, and Stripe's webhook. Writes are the
admin's."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.pages import to_platform
from glyphh_server.models import Org
from glyphh_server.ops.billing import changes, checkout, signature, webhook
from glyphh_server.ops.billing.checkout import StripePage
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.org import OrgView
from glyphh_server.ops.usage import Usage, usage

router = APIRouter(tags=["plans and billing"])


def stripe_client(request: Request) -> StripeClient:
    settings = request.app.state.settings
    return StripeClient(request.app.state.http, settings.stripe_secret_key, settings.stripe_meter_hosting)


Stripe = Annotated[StripeClient, Depends(stripe_client)]


PlanName = Annotated[str, Field(min_length=1, max_length=40, description="The plan's name, as /v1/plans lists it")]


class CheckoutIn(BaseModel):
    plan: PlanName


class PlanIn(BaseModel):
    plan: PlanName


class BillingView(Usage):
    billing_status: str
    renews_at: datetime | None = Field(description="When the subscription renews; null when not subscribed or ending")
    plan_until: datetime | None = Field(description="When an Enterprise grant ends; null on any other plan")


@router.get("/v1/billing", operation_id="billing")
async def get_billing(caller: Caller, conn: Conn) -> BillingView:
    """The org's billing: its plan and price, the precedents its hosted runtimes hold of the plan's managed bucket,
    and its hosting this month, all in, machine by machine."""
    row = (
        await conn.execute(select(Org.billing_status, Org.renews_at, Org.plan_until).where(Org.id == caller.org_id))
    ).one()
    return BillingView(**(await usage(conn, caller.org_id)).model_dump(), **row._mapping)


@router.post("/v1/billing/checkout", operation_id="startCheckout")
async def start_checkout(body: CheckoutIn, caller: Caller, conn: Conn, stripe: Stripe, request: Request) -> StripePage:
    """Stripe Checkout's address for a self-serve plan (Pro or Team), to open in the browser pane."""
    return await checkout.checkout(conn, caller, stripe, request.app.state.settings, body.plan)


@router.post("/v1/billing/plan", operation_id="changePlan")
async def change_plan(body: PlanIn, caller: Caller, conn: Conn, stripe: Stripe) -> OrgView:
    """Change plan: the newest version of another self-serve plan, prorated; or Free, which cancels the subscription
    now once the org has no hosted machines."""
    return await changes.change_plan(conn, caller, stripe, body.plan)


@router.post("/v1/billing/portal", operation_id="openBillingPortal")
async def open_portal(caller: Caller, conn: Conn, stripe: Stripe, request: Request) -> StripePage:
    """Stripe's portal address: card, invoices, cancel."""
    return await checkout.portal(conn, caller, stripe, request.app.state.settings)


@router.post("/v1/stripe/webhook", operation_id="stripeWebhook", status_code=204)
async def stripe_webhook(
    request: Request, conn: Conn, stripe_signature: Annotated[str | None, Header()] = None
) -> Response:
    """Stripe's events keep orgs true: plan version and status. Signed by Stripe, or refused."""
    secret = request.app.state.settings.stripe_webhook_secret
    event = signature.verified_event(secret, await request.body(), stripe_signature)
    await webhook.handle_event(conn, stripe_client(request), event)
    return Response(status_code=204)


@router.get(checkout.RETURN_PATH, include_in_schema=False)
async def billing_done(request: Request) -> Response:
    """Where Stripe's pages send the person back to: on to the platform's `/billing?done=1`."""
    return to_platform(request.app.state.settings, "/billing", done="1")
