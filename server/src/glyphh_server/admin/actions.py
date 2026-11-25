"""What staff may change on an org, besides Enterprise (ops/enterprise.py, reused as it is): the plan version it is on,
and suspending it. A plan version is changed only where billing can't disagree: to another version of the plan it
pays for, or, with no subscription, to any self-serve plan's; Enterprise is granted (with its contract's subscription)
and revoked, never set here. Suspended, its people's tokens, its connector and its API keys are refused until it is
lifted (api/auth.py, glyphh_ada/keys.py); nothing of its data changes. A grant adds to its hosted models' overage
balance. Each is audited by the request's row."""

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.seed import ENTERPRISE
from glyphh_server.errors import Conflict, NotFound
from glyphh_server.llm import ledger
from glyphh_server.models import Org, Plan, PlanVersion


class PlanChange(BaseModel):
    plan_version_id: uuid.UUID


class Suspension(BaseModel):
    reason: str = Field(min_length=3, max_length=500, description="Why, kept with it and in the audit log")


class BalanceGrant(BaseModel):
    amount_cents: int = Field(ge=1, le=100_000, description="US cents added to the hosted models' overage balance")
    note: str = Field(min_length=3, max_length=500, description="Why, kept on the ledger's entry and in the audit log")


async def grant_balance(conn: AsyncConnection, org_id: uuid.UUID, grant: BalanceGrant) -> None:
    """Money added to the org's overage balance (docs/specs/tokens.md), as a grant entry on its ledger."""
    await _org(conn, org_id)
    await ledger.credit(conn, org_id, "grant", grant.amount_cents * ledger.MICROS_PER_CENT, note=grant.note.strip())


async def _org(conn: AsyncConnection, org_id: uuid.UUID) -> Any:
    found = select(Org.id, Org.plan_version_id, Org.stripe_subscription_id, Org.plan_until, Org.suspended_at)
    row = (await conn.execute(found.where(Org.id == org_id).with_for_update())).first()
    if row is None:
        raise NotFound("There is no such org.", org_id=str(org_id))
    return row


async def _plan_of(conn: AsyncConnection, version_id: uuid.UUID) -> Any:
    found = select(Plan.name, PlanVersion.id, PlanVersion.version, PlanVersion.self_serve).join(
        Plan, Plan.id == PlanVersion.plan_id
    )
    row = (await conn.execute(found.where(PlanVersion.id == version_id))).first()
    if row is None:
        raise NotFound("There is no such plan version.", plan_version_id=str(version_id))
    return row


async def change_plan(conn: AsyncConnection, org_id: uuid.UUID, version_id: uuid.UUID) -> dict[str, Any]:
    """The org on that version; answers what it was on and is on now, for the audit log."""
    org = await _org(conn, org_id)
    now, wanted = await _plan_of(conn, org.plan_version_id), await _plan_of(conn, version_id)
    if ENTERPRISE in (now.name, wanted.name) and now.name != wanted.name:
        raise Conflict("Grant or revoke Enterprise instead.", reason="enterprise")
    if org.stripe_subscription_id and wanted.name != now.name:
        raise Conflict(
            "The org pays for its plan: change it in Stripe, or move it within the plan.", reason="subscribed"
        )
    if not org.stripe_subscription_id and not wanted.self_serve and wanted.name != now.name:
        raise Conflict("That plan is sold by contract.", reason="contract")
    await conn.execute(update(Org).where(Org.id == org_id).values(plan_version_id=version_id))
    return {"from": f"{now.name} v{now.version}", "to": f"{wanted.name} v{wanted.version}"}


async def suspend(conn: AsyncConnection, org_id: uuid.UUID, reason: str, own_org: uuid.UUID) -> None:
    if org_id == own_org:
        raise Conflict("You can't suspend your own org.", reason="own_org")
    org = await _org(conn, org_id)
    if org.suspended_at is not None:
        raise Conflict("The org is suspended already.", reason="suspended")
    await conn.execute(
        update(Org).where(Org.id == org_id).values(suspended_at=func.now(), suspended_reason=reason.strip())
    )


async def unsuspend(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    org = await _org(conn, org_id)
    if org.suspended_at is None:
        raise Conflict("The org is not suspended.", reason="not_suspended")
    await conn.execute(update(Org).where(Org.id == org_id).values(suspended_at=None, suspended_reason=None))
