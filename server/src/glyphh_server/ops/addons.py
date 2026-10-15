"""The add-on catalog: every mod but Workspaces, sold as a line on the org's subscription. Each add-on's newest version
on sale, the versions an org has, the plans each may be added to, and the mod's limits on each plan."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.seed import FREE
from glyphh_server.db.seed_addons import EVERY_PLAN
from glyphh_server.errors import Conflict, Invalid
from glyphh_server.models import Addon, Mod, Org, OrgAddon
from glyphh_server.ops.plans import ModLimits, org_version

COLUMNS = (
    Addon.id,
    Addon.mod,
    Addon.version,
    Addon.stripe_price_id,
    Addon.price_cents,
    Addon.per_seat,
    Addon.plans,
    Addon.free,
    Addon.limits,
    Mod.name,
    Mod.description,
    Mod.sort,
)


class AddonView(BaseModel):
    mod: str
    name: str
    description: str
    version: int
    price_cents: int = Field(description="A month: per seat when per_seat, else flat")
    per_seat: bool
    monthly_cents: int = Field(description="What it costs a month for the org's seats now")
    plans: list[str] = Field(description="The paid plans it may be added to")
    free: bool = Field(description="Whether a Free org may have it")
    allowed: bool = Field(description="Whether the org's plan may have it")
    limits: dict[str, int | None] | None = Field(
        description="The mod's limits on the org's plan; null when not allowed"
    )
    added: bool
    quantity: int | None = Field(description="On the subscription; null when not added")


def allowed(row: Row, plan: str) -> bool:
    return plan in row.plans or (plan == FREE and row.free)


def limits_on(row: Row, plan: str) -> dict[str, int | None]:
    """The mod's limits on this plan: the plan's own, else every plan's, sorted by name."""
    return dict(sorted(row.limits.get(plan, row.limits.get(EVERY_PLAN, {})).items()))


def quantity(row: Row, seats: int) -> int:
    return seats if row.per_seat else 1


async def newest_addons(conn: AsyncConnection) -> list[Row]:
    """Each add-on's newest version, when it is on sale and its mod is active, in the catalog's order."""
    latest = select(Addon.id).ext(distinct_on(Addon.mod)).order_by(Addon.mod, Addon.version.desc()).subquery()
    query = (
        select(*COLUMNS)
        .join(Mod, Mod.slug == Addon.mod)
        .where(Addon.id.in_(select(latest.c.id)), Addon.active, Mod.active)
        .order_by(Mod.sort, Mod.slug)
    )
    return list(await conn.execute(query))


async def sold_addon(conn: AsyncConnection, mod: str) -> Row:
    found = next((r for r in await newest_addons(conn) if r.mod == mod.strip().lower()), None)
    if found is None or found.stripe_price_id is None:
        raise Invalid("There is no such add-on on sale.", mod=mod, reason="no_addon")
    return found


async def org_addons(conn: AsyncConnection, org_id: uuid.UUID) -> list[Row]:
    """The add-ons the org has (active on its subscription), at the version each sells, when its mod is active."""
    query = (
        select(*COLUMNS, OrgAddon.stripe_item_id, OrgAddon.quantity.label("quantity_now"))
        .join(Addon, Addon.id == OrgAddon.addon_id)
        .join(Mod, Mod.slug == OrgAddon.mod)
        .where(OrgAddon.org_id == org_id, OrgAddon.status == "active", Mod.active)
        .order_by(Mod.sort, Mod.slug)
    )
    return list(await conn.execute(query))


async def licensed(conn: AsyncConnection, org_id: uuid.UUID, plan: str) -> dict[str, ModLimits]:
    """The mods the org's add-ons bring, each with its limits on the org's plan."""
    return {row.mod: ModLimits(limits=limits_on(row, plan)) for row in await org_addons(conn, org_id)}


def view(row: Row, plan: str, seats: int, have: Row | None) -> AddonView:
    ok = allowed(row, plan)
    return AddonView(
        mod=row.mod,
        name=row.name,
        description=row.description,
        version=row.version,
        price_cents=row.price_cents,
        per_seat=row.per_seat,
        monthly_cents=row.price_cents * quantity(row, seats),
        plans=list(row.plans),
        free=row.free,
        allowed=ok,
        limits=limits_on(row, plan) if ok or have else None,
        added=have is not None,
        quantity=None if have is None else have.quantity_now,
    )


async def check_allowed(conn: AsyncConnection, org_id: uuid.UUID, plan: str) -> None:
    """Every add-on the org has may be had on this plan, or the change of plan is refused."""
    for row in await org_addons(conn, org_id):
        if not allowed(row, plan):
            raise Conflict(
                f"The {row.name} add-on isn't sold with {plan}: remove it first.", reason="not_on_plan", mod=row.mod
            )


async def list_addons(conn: AsyncConnection, org_id: uuid.UUID) -> list[AddonView]:
    """Each add-on on sale, and each the org has at the version it added, in the catalog's order."""
    plan = (await org_version(conn, org_id)).name
    seats = (await conn.execute(select(Org.seats).where(Org.id == org_id))).scalar_one()
    have = {row.mod: row for row in await org_addons(conn, org_id)}
    rows = {row.mod: row for row in await newest_addons(conn)} | have
    ordered = sorted(rows.values(), key=lambda r: (r.sort, r.mod))
    return [view(row, plan, seats, have.get(row.mod)) for row in ordered]
