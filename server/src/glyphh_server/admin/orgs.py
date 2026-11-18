"""Every org, for staff, a page at a time: searched by its name, its id or a member's email, filtered by plan; with
its plan, members, where its sign-up came from and when it was made.

The platform's list still shows the retired products' numbers (Ada models, precedents, reads this month): those keys
are answered 0 until its screen drops them."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, Plan, PlanVersion, User

LIMIT_MAX: int = 200
COLUMNS = (Org.id, Org.name, Org.billing_status, Org.source, Org.created_at, Org.first_paid_at, Org.suspended_at)


class OrgRow(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    plan_version: int
    billing_status: str
    members: int
    source: str | None = Field(description="utm_source / utm_medium of its sign-up; null when untagged")
    created_at: datetime
    first_paid_at: datetime | None
    suspended: bool
    models: int = Field(0, description="Retired with the products: always 0")
    precedents: int = Field(0, description="Retired with the products: always 0")
    reads_month: int = Field(0, description="Retired with the products: always 0")


class OrgPage(BaseModel):
    orgs: list[OrgRow]
    total: int
    offset: int
    limit: int


def label(source: dict[str, Any] | None) -> str | None:
    """A sign-up's source, short: its utm_source and utm_medium, else the ad click id it carried."""
    if not source:
        return None
    clicked = next(
        (n for k, n in (("gclid", "google"), ("fbclid", "meta"), ("rdt_cid", "reddit")) if k in source), None
    )
    shown = [p for p in (source.get("utm_source") or clicked, source.get("utm_medium")) if p]
    return " / ".join(shown) or "(landing only)"


def _matching(found: Select[Any], q: str | None, plan: str | None) -> Select[Any]:
    if plan:
        found = found.where(Plan.name == plan)
    if q and q.strip():
        like = f"%{q.strip()}%"
        member = select(User.id).where(User.org_id == Org.id, User.email.ilike(like)).exists()
        found = found.where(or_(Org.name.ilike(like), cast(Org.id, Text) == q.strip().lower(), member))
    return found


async def orgs(conn: AsyncConnection, q: str | None, plan: str | None, offset: int = 0, limit: int = 50) -> OrgPage:
    members = select(func.count()).where(User.org_id == Org.id).scalar_subquery()
    base = (
        select(*COLUMNS, Plan.name.label("plan"), PlanVersion.version, members.label("members"))
        .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
        .join(Plan, Plan.id == PlanVersion.plan_id)
    )
    found = _matching(base, q, plan)
    total = (await conn.execute(select(func.count()).select_from(found.subquery()))).scalar_one()
    rows = await conn.execute(found.order_by(Org.created_at.desc(), Org.id).offset(offset).limit(limit))
    page = [
        OrgRow(
            id=r.id,
            name=r.name,
            plan=r.plan,
            plan_version=r.version,
            billing_status=r.billing_status,
            members=r.members,
            source=label(r.source),
            created_at=r.created_at,
            first_paid_at=r.first_paid_at,
            suspended=r.suspended_at is not None,
        )
        for r in rows
    ]
    return OrgPage(orgs=page, total=total, offset=offset, limit=limit)
