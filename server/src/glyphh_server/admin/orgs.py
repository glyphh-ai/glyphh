"""Every org, for staff, a page at a time: searched by its name, its id or a member's email, filtered by plan; with
its plan, members, Ada models and precedents (admin/adascan.py), reads this month (Redis's live count, else the
tick's), where its sign-up came from and when it was made."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import Row, Select, Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import requests
from glyphh_server.admin import adascan
from glyphh_server.models import AdaUsage, Org, Plan, PlanVersion, User

LIMIT_MAX: int = 200
COLUMNS = (Org.id, Org.name, Org.billing_status, Org.source, Org.created_at, Org.first_paid_at, Org.suspended_at)


class OrgRow(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    plan_version: int
    billing_status: str
    members: int
    models: int
    precedents: int
    reads_month: int
    source: str | None = Field(description="utm_source / utm_medium of its sign-up; null when untagged")
    created_at: datetime
    first_paid_at: datetime | None
    suspended: bool


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


async def _reads(conn: AsyncConnection, redis: Redis, orgs: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    month = requests.period()
    live = await redis.mget([requests.total_key(o, month) for o in orgs]) if orgs else []
    kept = select(AdaUsage.org_id, AdaUsage.requests).where(AdaUsage.org_id.in_(orgs), AdaUsage.period == month)
    told = {o: int(n) for o, n in await conn.execute(kept)}
    return {o: int(n) if n is not None else told.get(o, 0) for o, n in zip(orgs, live, strict=True)}


async def orgs(
    conn: AsyncConnection, redis: Redis, q: str | None, plan: str | None, offset: int = 0, limit: int = 50
) -> OrgPage:
    members = select(func.count()).where(User.org_id == Org.id).scalar_subquery()
    base = (
        select(*COLUMNS, Plan.name.label("plan"), PlanVersion.version, members.label("members"))
        .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
        .join(Plan, Plan.id == PlanVersion.plan_id)
    )
    found = _matching(base, q, plan)
    total = (await conn.execute(select(func.count()).select_from(found.subquery()))).scalar_one()
    rows = list(await conn.execute(found.order_by(Org.created_at.desc(), Org.id).offset(offset).limit(limit)))
    ada = adascan.by_org(await adascan.scan(conn, redis))
    reads = await _reads(conn, redis, [r.id for r in rows])
    page = [_row(r, ada.get(r.id), reads[r.id]) for r in rows]
    return OrgPage(orgs=page, total=total, offset=offset, limit=limit)


def _row(org: Row[Any], held: adascan.OrgAda | None, reads: int) -> OrgRow:
    return OrgRow(
        id=org.id,
        name=org.name,
        plan=org.plan,
        plan_version=org.version,
        billing_status=org.billing_status,
        members=org.members,
        models=0 if held is None else len(held.live),
        precedents=0 if held is None else held.precedents,
        reads_month=reads,
        source=label(org.source),
        created_at=org.created_at,
        first_paid_at=org.first_paid_at,
        suspended=org.suspended_at is not None,
    )
