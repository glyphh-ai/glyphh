"""Revenue as the server holds it, never asking Stripe: each org's plan version and its subscription's status as
Stripe's webhook last left them (ops/billing/sync.py), and the reads past a month it reported to Stripe's meter.
MRR is every paying org's price a month (a year's price over twelve); an Enterprise deal's price is its contract's, not
held here, so those orgs are counted apart."""

from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.requests import period
from glyphh_server.models import AdaMeterEvent, Org, Plan, PlanVersion
from glyphh_server.ops.plans import OVERAGE_CENTS_PER_10K

PAYING: tuple[str, ...] = ("active", "past_due")  # what MRR counts: trialing has not paid yet


class PlanMix(BaseModel):
    plan: str
    orgs: int
    paying: int = Field(description="Of them, on a subscription that is active or past due")
    mrr_cents: int = Field(description="Their prices a month; 0 for a contract's (Enterprise)")


class Money(BaseModel):
    mrr_cents: int
    paying_orgs: int
    contract_orgs: int = Field(description="Paying on a contract (Enterprise): its price is not held here")
    trialing_orgs: int
    overage_cents_month: int = Field(description="Reads past a plan's month reported to Stripe this month, priced")
    plans: list[PlanMix]


def _monthly() -> object:
    """A version's price a month: a year's over twelve; null when set by contract or free."""
    return case(
        (PlanVersion.billing_interval == "year", PlanVersion.price_cents / 12),
        else_=PlanVersion.price_cents,
    )


async def money(conn: AsyncConnection) -> Money:
    paying = Org.billing_status.in_(PAYING)
    found = (
        select(
            Plan.name,
            func.count(Org.id),
            func.count(Org.id).filter(paying),
            func.coalesce(func.sum(_monthly()).filter(paying), 0),
            func.count(Org.id).filter(paying, PlanVersion.price_cents.is_(None)),
            func.count(Org.id).filter(Org.billing_status == "trialing"),
        )
        .join(PlanVersion, PlanVersion.id == Org.plan_version_id)
        .join(Plan, Plan.id == PlanVersion.plan_id)
        .group_by(Plan.name, Plan.sort)
        .order_by(Plan.sort)
    )
    rows = list(await conn.execute(found))
    plans = [PlanMix(plan=r[0], orgs=r[1], paying=r[2], mrr_cents=int(r[3])) for r in rows]
    over = select(func.coalesce(func.sum(AdaMeterEvent.requests), 0)).where(AdaMeterEvent.period == period())
    reads_over = int((await conn.execute(over)).scalar_one())
    return Money(
        mrr_cents=sum(p.mrr_cents for p in plans),
        paying_orgs=sum(p.paying for p in plans),
        contract_orgs=sum(r[4] for r in rows),
        trialing_orgs=sum(r[5] for r in rows),
        overage_cents_month=reads_over * OVERAGE_CENTS_PER_10K // 10_000,
        plans=plans,
    )
