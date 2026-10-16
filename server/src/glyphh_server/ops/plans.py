"""Plans as callers see them: each plan's newest version, and the version an org is pinned to, with the mods each
includes and each mod's limits: the active mods its mod_limits names."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import Mod, Org, Plan, PlanVersion


class Limits(BaseModel):
    members: int | None = Field(description="null = unlimited")
    installs: int | None = Field(description="null = unlimited; per user")


class ModLimits(BaseModel):
    limits: dict[str, int | None] = Field(
        description="Each of the mod's limits, per user: null = unlimited; a switch is 0 or 1"
    )


class PlanView(BaseModel):
    name: str
    version: int
    seat_price_cents: int
    limits: Limits
    mods: dict[str, ModLimits] = Field(description="The mods this version includes, by slug; a mod not here is not")


COLUMNS = (
    Plan.name,
    PlanVersion.id,
    PlanVersion.version,
    PlanVersion.stripe_price_id,
    PlanVersion.seat_price_cents,
    PlanVersion.max_members,
    PlanVersion.max_installs,
    PlanVersion.runtime_hours,
    PlanVersion.mod_limits,
)


async def active_mods(conn: AsyncConnection) -> list[str]:
    """Every active mod's slug, in the catalog's order."""
    return list((await conn.execute(select(Mod.slug).where(Mod.active).order_by(Mod.sort, Mod.slug))).scalars())


def included(row: Row, mods: list[str]) -> dict[str, ModLimits]:
    """The active mods a version includes, by slug, each with its limits, both sorted by name."""
    return {
        slug: ModLimits(limits=dict(sorted(row.mod_limits[slug].items())))
        for slug in sorted(row.mod_limits)
        if slug in mods
    }


def view(row: Row, mods: list[str]) -> PlanView:
    return PlanView(
        name=row.name,
        version=row.version,
        seat_price_cents=row.seat_price_cents,
        limits=Limits(members=row.max_members, installs=row.max_installs),
        mods=included(row, mods),
    )


async def org_plan(conn: AsyncConnection, org_id: uuid.UUID) -> PlanView:
    """The org's pinned version as callers see it."""
    return view(await org_version(conn, org_id), await active_mods(conn))


def _newest():  # type: ignore[no-untyped-def]
    """Each active plan's newest version, in the plans' own order."""
    latest = (
        select(PlanVersion.id)
        .ext(distinct_on(PlanVersion.plan_id))
        .order_by(PlanVersion.plan_id, PlanVersion.version.desc())
        .subquery()
    )
    return (
        select(*COLUMNS)
        .join(Plan, Plan.id == PlanVersion.plan_id)
        .where(PlanVersion.id.in_(select(latest.c.id)), Plan.active)
        .order_by(Plan.sort)
    )


async def newest_versions(conn: AsyncConnection) -> list[Row]:
    return list(await conn.execute(_newest()))


async def list_plans(conn: AsyncConnection) -> list[PlanView]:
    mods = await active_mods(conn)
    return [view(r, mods) for r in await newest_versions(conn)]


async def newest_version(conn: AsyncConnection, name: str) -> Row:
    found = next((r for r in await newest_versions(conn) if r.name.lower() == name.strip().lower()), None)
    if found is None:
        raise Invalid("There is no such plan.", plan=name)
    return found


async def org_version(conn: AsyncConnection, org_id: uuid.UUID) -> Row:
    """The version the org is pinned to (it moves only when its admin changes plan)."""
    return (
        await conn.execute(
            select(*COLUMNS)
            .join(Plan, Plan.id == PlanVersion.plan_id)
            .join(Org, Org.plan_version_id == PlanVersion.id)
            .where(Org.id == org_id)
        )
    ).one()
