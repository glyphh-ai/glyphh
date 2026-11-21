"""One org, for staff: its account and billing as the server holds them, its members (how they sign in, when last
seen), its use (reads by month and by day) and its Ada models and jobs as metadata (admin/adascan.py): names, counts
and times, never a spec, a case or a file. With the staff actions taken on it (admin_audit)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import requests
from glyphh_server.admin import adascan, audit
from glyphh_server.admin.users import PersonRow, people
from glyphh_server.errors import NotFound
from glyphh_server.llm import usage as llm_usage
from glyphh_server.models import (
    AdaModelDay,
    AdaUsage,
    AdminAudit,
    LicenseRecord,
    Org,
    Plan,
    PlanVersion,
    RuntimeKey,
    User,
)

DAYS: int = 30
MONTHS: int = 12


class Account(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    plan: str
    plan_version: int
    plan_version_id: uuid.UUID
    billing_status: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    renews_at: datetime | None
    plan_until: datetime | None
    first_paid_at: datetime | None
    suspended_at: datetime | None
    suspended_reason: str | None
    source: dict[str, Any] | None


class Month(BaseModel):
    period: str
    reads: int


class DayReads(BaseModel):
    day: date
    reads: int


class OrgDetail(BaseModel):
    account: Account
    members: list[PersonRow]
    reads_month: int
    months: list[Month]
    days: list[DayReads]
    models: list[adascan.AdaModel]
    jobs: list[adascan.AdaJob]
    api_keys: int
    licences: int
    balance: llm_usage.Balance  # the hosted models' overage balance (docs/specs/tokens.md); staff may grant to it
    audit: list[audit.AuditEntry]


ACCOUNT = (
    Org.id, Org.name, Org.created_at, Plan.name.label("plan"), PlanVersion.version.label("plan_version"),
    Org.plan_version_id, Org.billing_status, Org.stripe_customer_id, Org.stripe_subscription_id, Org.renews_at,
    Org.plan_until, Org.first_paid_at, Org.suspended_at, Org.suspended_reason, Org.source,
)  # fmt: skip


async def account(conn: AsyncConnection, org_id: uuid.UUID) -> Account:
    found = (
        select(*ACCOUNT)
        .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
        .join(Plan, Plan.id == PlanVersion.plan_id)
        .where(Org.id == org_id)
    )
    row = (await conn.execute(found)).first()
    if row is None:
        raise NotFound("There is no such org.", org_id=str(org_id))
    return Account(**row._mapping)


async def _use(conn: AsyncConnection, org_id: uuid.UUID) -> tuple[list[Month], list[DayReads]]:
    months = select(AdaUsage.period, AdaUsage.requests).where(AdaUsage.org_id == org_id)
    by_month = [Month(period=p, reads=n) for p, n in await conn.execute(months.order_by(AdaUsage.period.desc()))]
    since = datetime.now(UTC).date() - timedelta(days=DAYS - 1)
    read = (AdaModelDay.org_id == org_id, AdaModelDay.metric.like("read:%"), AdaModelDay.day >= since)
    days = select(AdaModelDay.day, func.sum(AdaModelDay.n)).where(*read).group_by(AdaModelDay.day)
    by_day = {d: int(n) for d, n in await conn.execute(days)}
    every = [since + timedelta(days=i) for i in range(DAYS)]
    return by_month[:MONTHS], [DayReads(day=d, reads=by_day.get(d, 0)) for d in every]


async def _count(conn: AsyncConnection, query: Any) -> int:
    return int((await conn.execute(select(func.count()).select_from(query.subquery()))).scalar_one())


async def detail(conn: AsyncConnection, org_id: uuid.UUID) -> OrgDetail:
    shown = await account(conn, org_id)
    months, days = await _use(conn, org_id)
    month = next((m.reads for m in months if m.period == requests.period()), 0)
    ada = await adascan.one(conn, org_id)
    keys = select(RuntimeKey.id).join(User, User.id == RuntimeKey.user_id).where(User.org_id == org_id)
    keys = keys.where(RuntimeKey.scope == "cloud", RuntimeKey.revoked_at.is_(None))
    licences = select(LicenseRecord.id).where(LicenseRecord.org_id == org_id, LicenseRecord.revoked_at.is_(None))
    taken = select(AdminAudit).where(AdminAudit.org_id == org_id).order_by(AdminAudit.at.desc()).limit(20)
    return OrgDetail(
        account=shown,
        members=(await people(conn, org_id=org_id)).people,
        reads_month=month,
        months=months,
        days=days,
        models=ada.models,
        jobs=ada.jobs,
        api_keys=await _count(conn, keys),
        licences=await _count(conn, licences),
        balance=await llm_usage.balance(conn, org_id),
        audit=[audit.AuditEntry(**r._mapping) for r in await conn.execute(taken)],
    )
