"""Keeping the org true to its Stripe subscription: the plan version its plan item sells and its status. A
subscription that has ended puts the org back on Free; an Enterprise deal's has no plan item, so its plan stays."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.seed import FREE
from glyphh_server.models import BILLING_STATUSES, Org
from glyphh_server.obs.logs import fields
from glyphh_server.ops.billing.items import classify
from glyphh_server.ops.plans import newest_version

log = logging.getLogger("glyphh.billing")

ENDED: frozenset[str] = frozenset({"canceled", "incomplete_expired"})


def period_end(sub: dict[str, Any]) -> datetime | None:
    """The paid period's end: on its item in newer Stripe versions, on it in older ones."""
    end = sub["items"]["data"][0].get("current_period_end") or sub.get("current_period_end")
    return datetime.fromtimestamp(int(end), UTC) if end else None


def renews_at(sub: dict[str, Any]) -> datetime | None:
    """When the subscription renews: the period's end, unless it ends then."""
    return None if sub.get("cancel_at_period_end") else period_end(sub)


async def sync_subscription(conn: AsyncConnection, org_id: uuid.UUID, sub: dict[str, Any]) -> None:
    current = (await conn.execute(select(Org.stripe_subscription_id).where(Org.id == org_id))).scalar_one()
    if current not in (None, sub["id"]):
        log.info("stale subscription ignored", extra=fields(org=str(org_id), subscription=sub["id"]))
        return
    status = sub["status"] if sub["status"] in BILLING_STATUSES else "none"
    if status in ENDED:
        free = await newest_version(conn, FREE)
        values: dict[str, Any] = {"plan_version_id": free.id, "stripe_subscription_id": None, "renews_at": None}
        values |= {"plan_until": None}  # an Enterprise deal's subscription ended: so has the deal
    else:
        found = await classify(conn, org_id, sub)
        values = {"stripe_subscription_id": sub["id"], "renews_at": renews_at(sub)}
        if found.plan is not None:
            values["plan_version_id"] = found.plan_version_id
        if status == "active":  # its first payment: a paid conversion (the staff view)
            values["first_paid_at"] = func.coalesce(Org.first_paid_at, func.now())
    await conn.execute(
        update(Org).where(Org.id == org_id).values(**values, billing_status=status, stripe_customer_id=sub["customer"])
    )
