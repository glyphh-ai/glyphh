"""One org, for staff: its account and billing as the server holds them, its prepaid balance (money held for it: owed
back when above zero), its members (how they sign in, when last seen) and the staff actions taken on it
(admin_audit).

The platform's page still shows the retired products' parts (reads by month and day, Ada models and jobs, API keys,
licences): those keys are answered empty until its screen drops them."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.admin import audit
from glyphh_server.admin.users import PersonRow, people
from glyphh_server.errors import NotFound
from glyphh_server.models import AdminAudit, LlmBalance, Org, Plan, PlanVersion

LOW_MICROS: int = 5_000_000


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


class Balance(BaseModel):
    cents: float = Field(description="The prepaid balance in cents (fractional)")
    micros: int = Field(description="The same in microdollars (1 = $0.000001), exact")
    low: bool = Field(description="Under $5")


class OrgDetail(BaseModel):
    account: Account
    members: list[PersonRow]
    balance: Balance
    audit: list[audit.AuditEntry]
    reads_month: int = Field(0, description="Retired with the products: always 0")
    months: list[Any] = Field([], description="Retired with the products: always empty")
    days: list[Any] = Field([], description="Retired with the products: always empty")
    models: list[Any] = Field([], description="Retired with the products: always empty")
    jobs: list[Any] = Field([], description="Retired with the products: always empty")
    api_keys: int = Field(0, description="Retired with the products: always 0")
    licences: int = Field(0, description="Retired with the products: always 0")


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


async def balance(conn: AsyncConnection, org_id: uuid.UUID) -> Balance:
    held = (await conn.execute(select(LlmBalance.micros).where(LlmBalance.org_id == org_id))).scalar_one_or_none()
    micros = held or 0
    return Balance(cents=micros / 10_000, micros=micros, low=micros < LOW_MICROS)


async def detail(conn: AsyncConnection, org_id: uuid.UUID) -> OrgDetail:
    shown = await account(conn, org_id)
    taken = select(AdminAudit).where(AdminAudit.org_id == org_id).order_by(AdminAudit.at.desc()).limit(20)
    return OrgDetail(
        account=shown,
        members=(await people(conn, org_id=org_id)).people,
        balance=await balance(conn, org_id),
        audit=[audit.AuditEntry(**r._mapping) for r in await conn.execute(taken)],
    )
