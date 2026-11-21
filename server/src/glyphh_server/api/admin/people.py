"""People, plans, marketing (sign-ups by source), models by Ada version and the admin audit log, for staff."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from glyphh_server.admin import adascan, audit
from glyphh_server.admin.ada_versions import AdaVersions, by_version
from glyphh_server.admin.marketing import SourceRow, sources
from glyphh_server.admin.plans import PlanRow, plans
from glyphh_server.admin.users import PeoplePage, people
from glyphh_server.api.admin.deps import Staff

router = APIRouter()


@router.get("/users", operation_id="adminUsers")
async def list_users(
    staff: Staff,
    q: Annotated[str | None, Query(max_length=200, description="An email or a name")] = None,
    provider: Literal["google", "github"] | None = None,
    org_id: uuid.UUID | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> PeoplePage:
    return await people(staff.conn, q, provider, org_id, offset, limit)


@router.get("/plans", operation_id="adminPlans")
async def list_plans(staff: Staff) -> list[PlanRow]:
    """Every plan's versions: prices, Stripe ids, limits, cloud caps and the orgs on each."""
    return await plans(staff.conn)


@router.get("/marketing", operation_id="adminMarketing")
async def marketing(staff: Staff, days: Annotated[int, Query(ge=1, le=3660)] = 90) -> list[SourceRow]:
    """Sign-ups and paid conversions by source, medium and campaign, of the last `days` days."""
    return await sources(staff.conn, days)


@router.get("/ada-versions", operation_id="adminAdaVersions")
async def ada_versions(staff: Staff) -> AdaVersions:
    """Live models by the Ada version their active version runs."""
    return by_version(await adascan.scan(staff.conn, staff.request.app.state.redis))


@router.get("/audit", operation_id="adminAudit")
async def audit_log(
    staff: Staff,
    by: Annotated[str | None, Query(max_length=320, description="A staff member's email")] = None,
    org_id: uuid.UUID | None = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    before: datetime | None = None,
) -> audit.AuditPage:
    """Every staff request, newest first, a page at a time."""
    return await audit.listing(staff.conn, by, org_id, action, before)
