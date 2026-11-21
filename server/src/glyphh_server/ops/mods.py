"""The mods catalog: each active mod, and the plans that include it: every plan includes every active mod."""

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Mod
from glyphh_server.ops.plans import newest_versions


class ModView(BaseModel):
    slug: str
    name: str
    description: str
    plans: list[str] = Field(description="The plans that include it, in the plans' order: every one")


async def list_mods(conn: AsyncConnection) -> list[ModView]:
    plans = [row.name for row in await newest_versions(conn)]
    rows = await conn.execute(
        select(Mod.slug, Mod.name, Mod.description).where(Mod.active).order_by(Mod.sort, Mod.slug)
    )
    return [ModView(**row._mapping, plans=plans) for row in rows]
