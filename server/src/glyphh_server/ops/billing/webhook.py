"""Stripe's events, keeping orgs true: a finished checkout, a paid invoice, and every change to a subscription; a paid
top-up of the hosted models' overage balance credits it (ops/billing/topup.py). The
subscription is read fresh from Stripe, so events arriving late or out of order can't leave an org behind. A payment
(the checkout, each paid invoice) issues the org a licence key to the paid period's end; a subscription ended revokes
them (ops/billing/sync.py)."""

import logging
import uuid
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org
from glyphh_server.obs.logs import fields
from glyphh_server.ops.billing import topup
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.billing.sync import issue_paid, sync_subscription

log = logging.getLogger("glyphh.billing")

SUBSCRIPTION_EVENTS: frozenset[str] = frozenset(
    {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}
)


PAID: frozenset[str] = frozenset({"checkout.session.completed", "invoice.payment_succeeded"})


def _target(kind: str, obj: dict[str, Any]) -> tuple[str | None, str | None, str | None] | None:
    """What an event is about: the org id it was given, the customer and the subscription; None: of no interest. An
    invoice names its subscription on itself in older Stripe versions, under `parent` in newer ones."""
    if kind == "checkout.session.completed" and obj.get("mode") == "subscription":
        return obj.get("client_reference_id"), obj.get("customer"), obj.get("subscription")
    if kind == "invoice.payment_succeeded":
        details = (obj.get("parent") or {}).get("subscription_details") or {}
        sub_id = obj.get("subscription") or details.get("subscription")
        return (details.get("metadata") or {}).get("org_id"), obj.get("customer"), sub_id
    if kind in SUBSCRIPTION_EVENTS:
        return obj.get("metadata", {}).get("org_id"), obj.get("customer"), obj.get("id")
    return None


async def handle_event(
    conn: AsyncConnection,
    stripe: StripeClient,
    event: dict[str, Any],
    signing_key: Ed25519PrivateKey,
) -> None:
    kind, obj = event.get("type", ""), event.get("data", {}).get("object", {})
    if kind in topup.PAID_EVENTS and obj.get("mode") == "payment":  # the overage balance's top-up
        await topup.credited(conn, await _org(conn, obj.get("client_reference_id"), obj.get("customer")), obj)
        return
    target = _target(kind, obj)
    if target is None:
        log.info("stripe event ignored", extra=fields(type=kind))
        return
    given, customer, sub_id = target
    org_id = await _org(conn, given, customer)
    if org_id is None or not sub_id:
        log.warning("stripe event for no org", extra=fields(type=kind, customer=customer))
        return
    sub = await stripe.subscription(sub_id)
    await sync_subscription(conn, org_id, sub)
    if kind in PAID:
        await issue_paid(conn, signing_key, org_id, sub)


async def _org(conn: AsyncConnection, given: str | None, customer: str | None) -> uuid.UUID | None:
    """The org Stripe means: by the customer Glyphh made for it, else by the org id it was given."""
    by_customer = select(Org.id).where(Org.stripe_customer_id == customer)
    found = None if customer is None else (await conn.execute(by_customer)).scalar_one_or_none()
    if found is None and given:
        try:
            wanted = uuid.UUID(given)
        except ValueError:
            return None
        found = (await conn.execute(select(Org.id).where(Org.id == wanted))).scalar_one_or_none()
    return found
