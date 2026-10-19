"""Plans as callers see them: each plan's newest version, and the version an org is pinned to: its price, its limits
(hosted machines and the managed precedents) and its features. The markup on Fly's rates is a version's own and is
never shown. With GLYPHH_HOSTING off every plan shows no hosted machines (the versions themselves are unchanged)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.models import Mod, Org, Plan, PlanVersion


class Limits(BaseModel):
    machines: int | None = Field(
        description="Hosted machines on Glyphh's managed cloud, the org's together: null = unlimited, 0 = none (every "
        "plan's while hosting is off)"
    )
    precedents: int | None = Field(
        description="Managed precedents: what a hosted runtime may hold; null = unlimited. Local and self-hosted "
        "runtimes are unlimited on every plan"
    )


class Features(BaseModel):
    sync: bool = Field(description="Sync the precedent store across instances")
    ha: bool = Field(description="Highly available runtimes")
    offline: bool = Field(description="Offline (air-gapped) licences")
    sso: bool = Field(description="SSO and SAML, roles and audit logs")


class PlanView(BaseModel):
    name: str
    version: int
    price_cents: int | None = Field(description="A month's or a year's, as interval says; null: set in the contract")
    interval: Literal["month", "year"] | None = Field(description="null: free")
    self_serve: bool = Field(description="Bought with Stripe Checkout; else talk to sales@glyphh.ai")
    limits: Limits
    features: Features
    markup_hidden: Literal[True] = Field(True, description="The hosted rates already carry the plan's markup")


COLUMNS = (
    Plan.name,
    PlanVersion.id,
    PlanVersion.version,
    PlanVersion.stripe_price_id,
    PlanVersion.price_cents,
    PlanVersion.billing_interval,
    PlanVersion.self_serve,
    PlanVersion.max_machines,
    PlanVersion.precedents,
    PlanVersion.sync,
    PlanVersion.ha,
    PlanVersion.offline,
    PlanVersion.sso,
    PlanVersion.hosting_markup_pct,
)


async def active_mods(conn: AsyncConnection) -> list[str]:
    """Every active mod's slug, in the catalog's order: every plan includes each."""
    return list((await conn.execute(select(Mod.slug).where(Mod.active).order_by(Mod.sort, Mod.slug))).scalars())


def features(row: Row) -> Features:
    return Features(sync=row.sync, ha=row.ha, offline=row.offline, sso=row.sso)


def view(row: Row, settings: Settings) -> PlanView:
    return PlanView(
        name=row.name,
        version=row.version,
        price_cents=row.price_cents,
        interval=row.billing_interval,
        self_serve=row.self_serve,
        limits=Limits(machines=row.max_machines if settings.hosting else 0, precedents=row.precedents),
        features=features(row),
    )


async def org_plan(conn: AsyncConnection, org_id: uuid.UUID, settings: Settings) -> PlanView:
    """The org's pinned version as callers see it."""
    return view(await org_version(conn, org_id), settings)


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


async def list_plans(conn: AsyncConnection, settings: Settings) -> list[PlanView]:
    return [view(r, settings) for r in await newest_versions(conn)]


async def newest_version(conn: AsyncConnection, name: str) -> Row:
    found = next((r for r in await newest_versions(conn) if r.name.lower() == name.strip().lower()), None)
    if found is None:
        raise Invalid("There is no such plan.", plan=name)
    return found


async def org_version(conn: AsyncConnection, org_id: uuid.UUID) -> Row:
    """The version the org is pinned to (it moves only when its plan changes)."""
    return (
        await conn.execute(
            select(*COLUMNS)
            .join(Plan, Plan.id == PlanVersion.plan_id)
            .join(Org, Org.plan_version_id == PlanVersion.id)
            .where(Org.id == org_id)
        )
    ).one()
