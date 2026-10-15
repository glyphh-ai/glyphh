"""The mods catalog: each active mod, the plans whose newest version includes it, and the add-on it is sold as."""

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Mod
from glyphh_server.ops.addons import newest_addons
from glyphh_server.ops.plans import active_mods, included, newest_versions


class AddonOffer(BaseModel):
    price_cents: int = Field(description="A month: per seat when per_seat, else flat")
    per_seat: bool
    plans: list[str] = Field(description="The paid plans it may be added to")
    free: bool = Field(description="Whether a Free org may have it")


class ModView(BaseModel):
    slug: str
    name: str
    description: str
    plans: list[str] = Field(description="The plans whose newest version includes this mod, in the plans' order")
    addon: AddonOffer | None = Field(description="The add-on it is sold as, on sale now; null when it is not one")


async def list_mods(conn: AsyncConnection) -> list[ModView]:
    mods = await active_mods(conn)
    versions = [(row.name, included(row, mods)) for row in await newest_versions(conn)]
    offers = {
        row.mod: AddonOffer(price_cents=row.price_cents, per_seat=row.per_seat, plans=list(row.plans), free=row.free)
        for row in await newest_addons(conn)
    }
    rows = await conn.execute(
        select(Mod.slug, Mod.name, Mod.description).where(Mod.active).order_by(Mod.sort, Mod.slug)
    )
    return [
        ModView(
            **row._mapping,
            plans=[plan for plan, slugs in versions if row.slug in slugs],
            addon=offers.get(row.slug),
        )
        for row in rows
    ]
