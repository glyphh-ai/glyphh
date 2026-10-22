"""Plans as callers see them: each plan's newest version, and the version an org is pinned to: its price, its limits
(runtime nodes and precedents per node), its features, and with Ada Cloud on its cloud limits (precedents and reads
a month per org, calls a second). The markup on Fly's rates is a version's own and is never shown."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import Mod, Org, Plan, PlanVersion


class Limits(BaseModel):
    machines: int | None = Field(
        description="Runtime nodes, the org's together: every runtime node linked for it, hosted or self-hosted (only "
        "hosted machines are refused past it; the rest are counted, never refused); null = unlimited"
    )
    precedents: int | None = Field(
        description="Precedents per node, across all its Ada models: the licence key's max_precedents, enforced by "
        "rrotor; null = unlimited"
    )


class Features(BaseModel):
    sync: bool = Field(description="Sync the precedent store across instances")
    ha: bool = Field(description="Highly available runtimes")
    offline: bool = Field(description="Offline (air-gapped) licences")
    sso: bool = Field(description="SSO and SAML, roles and audit logs")


# What works today, one source of truth: only offline licences; the other features are licence flags, not built.
BUILT: Features = Features(sync=False, ha=False, offline=True, sso=False)
OVERAGE_CENTS_PER_10K: int = 100  # a metered plan's reads past its month: $1 per 10,000 (the ada_requests price)


class CloudLimits(BaseModel):
    """Ada Cloud's limits, the org's whatever its people, models or keys (never per seat)."""

    precedents: int | None = Field(description="Precedents the org may hold across its models; null = by contract")
    requests_per_month: int | None = Field(
        description="Reads (decide, query, probabilities, facts) a calendar month, UTC; null = by contract"
    )
    requests_per_second: int | None = Field(description="Calls a second, the org's together; null = by contract")
    overage: bool = Field(
        description="Reads past the month are metered (overage_cents_per_10k); false: refused until the month turns"
    )
    overage_cents_per_10k: int | None = Field(description="What 10,000 reads past the month cost; null: none sold")


class PlanView(BaseModel):
    name: str
    version: int
    price_cents: int | None = Field(description="A month's or a year's, as interval says; null: set in the contract")
    interval: Literal["month", "year"] | None = Field(description="null: free")
    self_serve: bool = Field(description="Bought with Stripe Checkout; else talk to sales@glyphh.ai")
    limits: Limits
    features: Features
    built: Features = Field(
        BUILT,
        description="Which features work today, the same on every plan: never show one as included that is not built",
    )
    markup_hidden: Literal[True] = Field(True, description="The hosted rates already carry the plan's markup")
    cloud: CloudLimits | None = Field(None, description="Ada Cloud's limits; null while Ada Cloud is off")


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
    PlanVersion.cloud_precedents,
    PlanVersion.cloud_requests,
    PlanVersion.cloud_rps,
    PlanVersion.cloud_overage,
)


async def active_mods(conn: AsyncConnection) -> list[str]:
    """Every active mod's slug, in the catalog's order: every plan includes each."""
    return list((await conn.execute(select(Mod.slug).where(Mod.active).order_by(Mod.sort, Mod.slug))).scalars())


def features(row: Row) -> Features:
    return Features(sync=row.sync, ha=row.ha, offline=row.offline, sso=row.sso)


def cloud_limits(row: Row) -> CloudLimits:
    return CloudLimits(
        precedents=row.cloud_precedents,
        requests_per_month=row.cloud_requests,
        requests_per_second=row.cloud_rps,
        overage=row.cloud_overage,
        overage_cents_per_10k=OVERAGE_CENTS_PER_10K if row.cloud_overage else None,
    )


def view(row: Row, cloud: bool = False) -> PlanView:
    """A version as callers see it; its cloud limits only with Ada Cloud on."""
    return PlanView(
        name=row.name,
        version=row.version,
        price_cents=row.price_cents,
        interval=row.billing_interval,
        self_serve=row.self_serve,
        limits=Limits(machines=row.max_machines, precedents=row.precedents),
        features=features(row),
        cloud=cloud_limits(row) if cloud else None,
    )


async def org_plan(conn: AsyncConnection, org_id: uuid.UUID, cloud: bool = False) -> PlanView:
    """The org's pinned version as callers see it."""
    return view(await org_version(conn, org_id), cloud)


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


async def list_plans(conn: AsyncConnection, cloud: bool = False) -> list[PlanView]:
    return [view(r, cloud) for r in await newest_versions(conn)]


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
