"""Plans as callers see them: each plan's newest version, and the version an org is pinned to: its price, its
features, and with Ada Cloud on its cloud limits (precedents and reads a month per org, calls a second)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import Org, Plan, PlanVersion


class Features(BaseModel):
    sso: bool = Field(description="Single sign-on with the org's own identity provider (OpenID Connect)")


BUILT: Features = Features(sso=True)  # what works today, one source of truth
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
    features: Features
    built: Features = Field(
        BUILT,
        description="Which features work today, the same on every plan: never show one as included that is not built",
    )
    cloud: CloudLimits | None = Field(None, description="Ada Cloud's limits; null while Ada Cloud is off")
    llm_tokens: int | None = Field(
        None,
        description="Glyphh-hosted models' tokens a calendar month, UTC, before tokens are charged to the overage "
        "balance at each model's rates (GET /v1/llm/models); null = by contract",
    )


COLUMNS = (
    Plan.name,
    PlanVersion.id,
    PlanVersion.version,
    PlanVersion.stripe_price_id,
    PlanVersion.price_cents,
    PlanVersion.billing_interval,
    PlanVersion.self_serve,
    PlanVersion.sso,
    PlanVersion.cloud_precedents,
    PlanVersion.cloud_requests,
    PlanVersion.cloud_rps,
    PlanVersion.cloud_overage,
    PlanVersion.llm_tokens,
)


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
        features=Features(sso=row.sso),
        cloud=cloud_limits(row) if cloud else None,
        llm_tokens=row.llm_tokens,
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
