"""Every plan and every version of it, for staff: prices, Stripe's price ids, Ada Cloud's caps and how many
orgs are on each version."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, Plan, PlanVersion


class VersionRow(BaseModel):
    id: uuid.UUID
    version: int
    price_cents: int | None
    billing_interval: str | None
    stripe_price_id: str | None
    self_serve: bool
    sso: bool
    cloud_precedents: int | None
    cloud_requests: int | None
    cloud_rps: int | None
    cloud_overage: bool
    created_at: datetime
    orgs: int
    newest: bool


class PlanRow(BaseModel):
    name: str
    active: bool
    orgs: int
    versions: list[VersionRow]


VERSION = (
    PlanVersion.id, PlanVersion.version, PlanVersion.price_cents, PlanVersion.billing_interval,
    PlanVersion.stripe_price_id, PlanVersion.self_serve, PlanVersion.sso, PlanVersion.cloud_precedents,
    PlanVersion.cloud_requests, PlanVersion.cloud_rps, PlanVersion.cloud_overage, PlanVersion.created_at,
)  # fmt: skip


async def plans(conn: AsyncConnection) -> list[PlanRow]:
    on = select(func.count()).where(Org.plan_version_id == PlanVersion.id).scalar_subquery()
    found = (
        select(Plan.name.label("plan"), Plan.active, *VERSION, on.label("orgs"))
        .join(Plan, Plan.id == PlanVersion.plan_id)
        .order_by(Plan.sort, Plan.name, PlanVersion.version.desc())
    )
    shown: dict[str, PlanRow] = {}
    for r in await conn.execute(found):
        row = shown.setdefault(r.plan, PlanRow(name=r.plan, active=r.active, orgs=0, versions=[]))
        values = {k: v for k, v in r._mapping.items() if k not in ("plan", "active")}
        row.versions.append(VersionRow(**values, newest=not row.versions))
        row.orgs += r.orgs
    return list(shown.values())
