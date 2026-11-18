"""Stripe's webhook: all that is left of billing. It records the old subscriptions' cancellations and last payments
on their orgs (ops/billing/webhook.py)."""

from typing import Annotated

from fastapi import APIRouter, Header, Request, Response

from glyphh_server.api.auth import Conn
from glyphh_server.ops.billing import signature, webhook
from glyphh_server.ops.billing.stripe import StripeClient

router = APIRouter(tags=["billing"])


@router.post("/v1/stripe/webhook", operation_id="stripeWebhook", status_code=204)
async def stripe_webhook(
    request: Request, conn: Conn, stripe_signature: Annotated[str | None, Header()] = None
) -> Response:
    """Stripe's events keep orgs true: plan version and status. Signed by Stripe, or refused."""
    settings = request.app.state.settings
    event = signature.verified_event(settings.stripe_webhook_secret, await request.body(), stripe_signature)
    stripe = StripeClient(request.app.state.http, settings.stripe_secret_key)
    await webhook.handle_event(conn, stripe, event)
    return Response(status_code=204)
