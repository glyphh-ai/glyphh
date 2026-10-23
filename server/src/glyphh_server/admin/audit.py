"""The admin audit log: every staff request, who made it (their user and verified email), what (the route's operation,
its path and query, and what an action changed), when, about which org, and how it ended (`ok`, or the refusal's
code). Written in the request's own transaction, so a refused or failed request leaves its own row, written apart
(api/admin/deps.py). Never shown to anyone but staff."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import AdminAudit
from glyphh_server.ops.auth.principal import Principal

PAGE: int = 100


class AuditEntry(BaseModel):
    id: uuid.UUID
    at: datetime
    staff_email: str
    action: str
    org_id: uuid.UUID | None
    target: str | None
    detail: dict[str, Any]
    outcome: str


class AuditPage(BaseModel):
    entries: list[AuditEntry]
    next_before: datetime | None


async def record(
    conn: AsyncConnection,
    who: Principal,
    action: str,
    org_id: uuid.UUID | None = None,
    target: str | None = None,
    detail: dict[str, Any] | None = None,
    outcome: str = "ok",
) -> uuid.UUID:
    values = {
        "staff_user_id": who.user_id,
        "staff_email": who.email.strip().lower(),
        "action": action,
        "org_id": org_id,
    }
    values |= {"target": target, "detail": detail or {}, "outcome": outcome}
    return (await conn.execute(insert(AdminAudit).values(**values).returning(AdminAudit.id))).scalar_one()


async def add(conn: AsyncConnection, entry: uuid.UUID, detail: dict[str, Any]) -> None:
    """What an action changed, added to its row."""
    await conn.execute(
        update(AdminAudit).where(AdminAudit.id == entry).values(detail=AdminAudit.detail.op("||")(detail))
    )


async def listing(
    conn: AsyncConnection,
    staff: str | None = None,
    org_id: uuid.UUID | None = None,
    action: str | None = None,
    before: datetime | None = None,
) -> AuditPage:
    """The newest entries first, a page at a time (the next page: entries before `next_before`)."""
    found = select(AdminAudit).order_by(AdminAudit.at.desc(), AdminAudit.id).limit(PAGE + 1)
    if staff:
        found = found.where(AdminAudit.staff_email == staff.strip().lower())
    if org_id is not None:
        found = found.where(AdminAudit.org_id == org_id)
    if action:
        found = found.where(AdminAudit.action == action)
    if before is not None:
        found = found.where(AdminAudit.at < before)
    rows = list(await conn.execute(found))
    entries = [AuditEntry(**r._mapping) for r in rows[:PAGE]]
    return AuditPage(entries=entries, next_before=entries[-1].at if len(rows) > PAGE else None)
