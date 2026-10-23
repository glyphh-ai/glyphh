"""The one door to the staff view: a staff member (admin/staff.py) signed in through the platform, or a refusal that
is itself logged (an ops event). The request's transaction then leaves the caller's org on purpose (db/tenancy.py),
so it sees every org's rows: this is the only API path that does, and every request on it is written to admin_audit
first, in that transaction; a request refused or failed has its row written apart, with the refusal's code. The
caller's own org's normal API is untouched: tenant isolation holds for every other caller."""

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.admin import audit
from glyphh_server.admin.staff import is_staff, via_platform
from glyphh_server.api.auth import Bearer, Conn, authenticate
from glyphh_server.db import tenancy
from glyphh_server.errors import Forbidden, GlyphhError
from glyphh_server.obs import context
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.principal import Principal

log = logging.getLogger("glyphh.staff")

NOT_STAFF: str = "This is for Glyphh's staff, signed in on the platform."
OUTCOMES: dict[type, str] = {RequestValidationError: "E_INVALID"}


@dataclass
class StaffCall:
    """A staff request: who, its transaction across every org, and its audit row."""

    who: Principal
    conn: AsyncConnection
    request: Request
    entry: uuid.UUID

    async def note(self, **detail: Any) -> None:
        """What the action changed, added to its audit row."""
        await audit.add(self.conn, self.entry, detail)


def _what(request: Request) -> tuple[str, uuid.UUID | None, dict[str, Any]]:
    """The route's operation, the org it is about (its path's org_id) and its path and query."""
    route = request.scope.get("route")
    action = getattr(route, "operation_id", None) or request.url.path
    org = request.path_params.get("org_id")
    try:
        org_id = uuid.UUID(str(org)) if org else None
    except ValueError:
        org_id = None
    return action, org_id, {"path": request.url.path, "query": dict(request.query_params)}


async def staff(request: Request, conn: Conn, creds: Bearer) -> AsyncIterator[StaffCall]:
    settings = request.app.state.settings
    who = await authenticate(conn, creds, settings.mcp_resource)
    if not (is_staff(settings, who) and via_platform(settings, who)):
        log.warning("staff view refused", extra=fields(user=str(who.user_id), path=request.url.path))
        raise Forbidden(NOT_STAFF, reason="not_staff")
    await tenancy.leave(conn)
    context.org_id.set(None)
    action, org_id, detail = _what(request)
    entry = await audit.record(conn, who, action, org_id, request.url.path, detail)
    try:
        yield StaffCall(who, conn, request, entry)
    except Exception as err:
        outcome = err.code if isinstance(err, GlyphhError) else OUTCOMES.get(type(err), "E_INTERNAL")
        engine: AsyncEngine = request.app.state.engine
        async with engine.begin() as apart:
            await audit.record(apart, who, action, org_id, request.url.path, detail, outcome)
        raise


Staff = Annotated[StaffCall, Depends(staff)]
