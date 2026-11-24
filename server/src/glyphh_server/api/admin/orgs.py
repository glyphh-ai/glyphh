"""Orgs, for staff: the list and one org; and the staff actions on one, each audited with what it changed: Enterprise
granted or revoked (ops/enterprise.py, as its command line does it), its plan version changed, suspended or lifted."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from glyphh_server.admin import actions
from glyphh_server.admin.actions import BalanceGrant, PlanChange, Suspension
from glyphh_server.admin.org_detail import OrgDetail, detail
from glyphh_server.admin.orgs import LIMIT_MAX, OrgPage, orgs
from glyphh_server.api.admin.deps import Staff
from glyphh_server.ops import enterprise
from glyphh_server.ops.billing.stripe import StripeClient

router = APIRouter()


class EnterpriseGrant(BaseModel):
    until: date = Field(description="The deal's last day (UTC)")
    subscription: str = Field(pattern=r"^sub_[A-Za-z0-9]+$", description="The deal's Stripe subscription")


class Done(BaseModel):
    message: str


@router.get("/orgs", operation_id="adminOrgs")
async def list_orgs(
    staff: Staff,
    q: Annotated[str | None, Query(max_length=200, description="A name, an org id or a member's email")] = None,
    plan: Annotated[str | None, Query(max_length=40)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = 50,
) -> OrgPage:
    return await orgs(staff.conn, staff.request.app.state.redis, q, plan, offset, limit)


@router.get("/orgs/{org_id}", operation_id="adminOrg")
async def get_org(org_id: uuid.UUID, staff: Staff) -> OrgDetail:
    """Its account, billing, members, use, and its models and jobs as metadata: never a spec, a case or a file."""
    return await detail(staff.conn, org_id)


@router.post("/orgs/{org_id}/enterprise", operation_id="adminGrantEnterprise")
async def grant_enterprise(org_id: uuid.UUID, body: EnterpriseGrant, staff: Staff) -> Done:
    """On Enterprise through `until`, billed on the deal's subscription."""
    state = staff.request.app.state
    stripe = StripeClient(state.http, state.settings.stripe_secret_key)  # without billing set up: E_UNAVAILABLE
    said = await enterprise.grant(state.engine, stripe, org_id, body.until, body.subscription)
    await staff.note(until=body.until.isoformat(), subscription=body.subscription)
    return Done(message=said)


@router.delete("/orgs/{org_id}/enterprise", operation_id="adminRevokeEnterprise")
async def revoke_enterprise(org_id: uuid.UUID, staff: Staff) -> Done:
    """Back on Free; its subscription is then cancelled in Stripe by hand."""
    said = await enterprise.revoke(staff.request.app.state.engine, org_id)
    return Done(message=said)


@router.post("/orgs/{org_id}/plan", operation_id="adminChangePlan")
async def change_plan(org_id: uuid.UUID, body: PlanChange, staff: Staff) -> Done:
    changed = await actions.change_plan(staff.conn, org_id, body.plan_version_id)
    await staff.note(**changed)
    return Done(message=f"Moved from {changed['from']} to {changed['to']}.")


@router.post("/orgs/{org_id}/llm-grant", operation_id="adminGrantBalance")
async def grant_balance(org_id: uuid.UUID, body: BalanceGrant, staff: Staff) -> Done:
    """Dollars added to the org's hosted-model overage balance, a grant on its ledger with the note."""
    await actions.grant_balance(staff.conn, org_id, body)
    await staff.note(amount_cents=body.amount_cents, note=body.note)
    return Done(message=f"Granted ${body.amount_cents / 100:,.2f} to its overage balance.")


@router.post("/orgs/{org_id}/suspend", operation_id="adminSuspendOrg", status_code=204)
async def suspend(org_id: uuid.UUID, body: Suspension, staff: Staff) -> Response:
    await actions.suspend(staff.conn, org_id, body.reason, staff.who.org_id)
    await staff.note(reason=body.reason)
    return Response(status_code=204)


@router.delete("/orgs/{org_id}/suspend", operation_id="adminUnsuspendOrg", status_code=204)
async def unsuspend(org_id: uuid.UUID, staff: Staff) -> Response:
    await actions.unsuspend(staff.conn, org_id)
    return Response(status_code=204)
