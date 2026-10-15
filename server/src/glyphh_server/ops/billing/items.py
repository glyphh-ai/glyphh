"""A Stripe subscription's items as Glyphh sells them: the plan's item (its price a plan version's) and one item per
add-on (its price an add-on version's); and the org's add-ons kept true to them."""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Row, func, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Addon, OrgAddon, PlanVersion
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.billing")


@dataclass(frozen=True, slots=True)
class AddonItem:
    item: dict[str, Any]
    addon: Row


@dataclass(slots=True)
class Items:
    plan: dict[str, Any] | None = None
    plan_version_id: uuid.UUID | None = None
    addons: dict[str, AddonItem] = field(default_factory=dict)


async def classify(conn: AsyncConnection, org_id: uuid.UUID, sub: dict[str, Any]) -> Items:
    """Each item by its price: the plan's, an add-on's, or unknown (logged and left alone)."""
    items = sub["items"]["data"]
    prices = [item["price"]["id"] for item in items]
    sold = select(PlanVersion.stripe_price_id, PlanVersion.id).where(PlanVersion.stripe_price_id.in_(prices))
    plans = {row.stripe_price_id: row.id for row in await conn.execute(sold)}
    columns = (Addon.id, Addon.mod, Addon.per_seat, Addon.stripe_price_id)
    addons = {
        row.stripe_price_id: row
        for row in await conn.execute(select(*columns).where(Addon.stripe_price_id.in_(prices)))
    }
    found = Items()
    for item in items:
        price = item["price"]["id"]
        if price in plans and found.plan is None:
            found.plan, found.plan_version_id = item, plans[price]
        elif price in addons:
            found.addons[addons[price].mod] = AddonItem(item, addons[price])
        else:
            log.warning("unknown stripe price", extra=fields(org=str(org_id), price=price))
    return found


async def sync_addons(conn: AsyncConnection, org_id: uuid.UUID, found: dict[str, AddonItem]) -> None:
    """The org has exactly the add-ons on its subscription: each there active with its item and quantity, every other
    removed. Applying the same subscription again changes nothing."""
    for mod, on in found.items():
        values = {
            "addon_id": on.addon.id,
            "stripe_item_id": on.item["id"],
            "quantity": max(1, int(on.item["quantity"])),
            "status": "active",
            "updated_at": func.now(),
        }
        await conn.execute(
            upsert(OrgAddon)
            .values(org_id=org_id, mod=mod, **values)
            .on_conflict_do_update(index_elements=[OrgAddon.org_id, OrgAddon.mod], set_=values)
        )
    await conn.execute(
        update(OrgAddon)
        .where(OrgAddon.org_id == org_id, OrgAddon.status == "active", OrgAddon.mod.not_in(list(found)))
        .values(status="removed", stripe_item_id=None, updated_at=func.now())
    )
