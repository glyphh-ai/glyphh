"""A Stripe subscription's items as Glyphh sells them: the plan's flat item (its price a plan version's) and the
metered hosting item (passed over: the meter, not the item, says what it charges)."""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import PlanVersion
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.billing")


@dataclass(slots=True)
class Items:
    plan: dict[str, Any] | None = None
    plan_version_id: uuid.UUID | None = None


def metered(item: dict[str, Any]) -> bool:
    return (item["price"].get("recurring") or {}).get("usage_type") == "metered"


async def classify(conn: AsyncConnection, org_id: uuid.UUID, sub: dict[str, Any]) -> Items:
    """The plan's item by its price; a metered item passes; anything else is logged and left alone."""
    items = sub["items"]["data"]
    prices = [item["price"]["id"] for item in items]
    sold = select(PlanVersion.stripe_price_id, PlanVersion.id).where(PlanVersion.stripe_price_id.in_(prices))
    plans = {row.stripe_price_id: row.id for row in await conn.execute(sold)}
    found = Items()
    for item in items:
        price = item["price"]["id"]
        if price in plans and found.plan is None:
            found.plan, found.plan_version_id = item, plans[price]
        elif not metered(item):
            log.warning("unknown stripe price", extra=fields(org=str(org_id), price=price))
    return found
