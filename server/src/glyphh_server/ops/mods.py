"""The mods catalog: each active mod and the plans whose newest version includes it."""

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Mod
from glyphh_server.ops.plans import active_mods, included, newest_versions


class ModView(BaseModel):
    slug: str
    name: str
    description: str
    plans: list[str] = Field(description="The plans whose newest version includes this mod, in the plans' order")


async def list_mods(conn: AsyncConnection) -> list[ModView]:
    mods = await active_mods(conn)
    versions = [(row.name, included(row, mods)) for row in await newest_versions(conn)]
    rows = await conn.execute(
        select(Mod.slug, Mod.name, Mod.description).where(Mod.active).order_by(Mod.sort, Mod.slug)
    )
    return [ModView(**row._mapping, plans=[plan for plan, slugs in versions if row.slug in slugs]) for row in rows]
