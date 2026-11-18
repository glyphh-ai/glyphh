"""Orgs, for staff: the list and one org; and the staff actions left on one, each audited with what it changed:
suspended or lifted."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from glyphh_server.admin import actions
from glyphh_server.admin.actions import Suspension
from glyphh_server.admin.org_detail import OrgDetail, detail
from glyphh_server.admin.orgs import LIMIT_MAX, OrgPage, orgs
from glyphh_server.api.admin.deps import Staff

router = APIRouter()


@router.get("/orgs", operation_id="adminOrgs")
async def list_orgs(
    staff: Staff,
    q: Annotated[str | None, Query(max_length=200, description="A name, an org id or a member's email")] = None,
    plan: Annotated[str | None, Query(max_length=40)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=LIMIT_MAX)] = 50,
) -> OrgPage:
    return await orgs(staff.conn, q, plan, offset, limit)


@router.get("/orgs/{org_id}", operation_id="adminOrg")
async def get_org(org_id: uuid.UUID, staff: Staff) -> OrgDetail:
    """Its account, billing as Stripe's webhook last left it, its prepaid balance and its members."""
    return await detail(staff.conn, org_id)


@router.post("/orgs/{org_id}/suspend", operation_id="adminSuspendOrg", status_code=204)
async def suspend(org_id: uuid.UUID, body: Suspension, staff: Staff) -> Response:
    await actions.suspend(staff.conn, org_id, body.reason, staff.who.org_id)
    await staff.note(reason=body.reason)
    return Response(status_code=204)


@router.delete("/orgs/{org_id}/suspend", operation_id="adminUnsuspendOrg", status_code=204)
async def unsuspend(org_id: uuid.UUID, staff: Staff) -> Response:
    await actions.unsuspend(staff.conn, org_id)
    return Response(status_code=204)
