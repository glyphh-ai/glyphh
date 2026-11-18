"""Every person, for staff, a page at a time: searched by email or name, filtered by how they sign in or by org; with
their org, role, sign-in providers, when they joined and when last seen (their newest use of a sign-in grant, marked
at most once a minute)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by, array_agg
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import ConnectorGrant, Identity, Org, User


class PersonRow(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    org_id: uuid.UUID
    org_name: str
    providers: list[str]
    created_at: datetime
    last_seen_at: datetime | None
    source: dict[str, Any] | None


class PeoplePage(BaseModel):
    people: list[PersonRow]
    total: int
    offset: int
    limit: int


def _seen() -> Any:
    return select(func.max(ConnectorGrant.last_used_at)).where(ConnectorGrant.user_id == User.id).scalar_subquery()


def _providers() -> Any:
    ordered = aggregate_order_by(Identity.provider, Identity.provider)
    return select(array_agg(ordered)).where(Identity.user_id == User.id).scalar_subquery()


def _matching(found: Select[Any], q: str | None, provider: str | None, org_id: uuid.UUID | None) -> Select[Any]:
    if q and q.strip():
        like = f"%{q.strip()}%"
        found = found.where(or_(User.email.ilike(like), User.name.ilike(like)))
    if provider:
        found = found.where(
            select(Identity.user_id).where(Identity.user_id == User.id, Identity.provider == provider).exists()
        )
    if org_id is not None:
        found = found.where(User.org_id == org_id)
    return found


async def people(
    conn: AsyncConnection,
    q: str | None = None,
    provider: str | None = None,
    org_id: uuid.UUID | None = None,
    offset: int = 0,
    limit: int = 200,
) -> PeoplePage:
    columns = (User.id, User.email, User.name, User.role, User.org_id, Org.name.label("org_name"), User.created_at)
    base = select(*columns, User.source, _providers().label("providers"), _seen().label("last_seen_at"))
    found = _matching(base.join(Org, Org.id == User.org_id), q, provider, org_id)
    total = (await conn.execute(select(func.count()).select_from(found.subquery()))).scalar_one()
    rows = await conn.execute(found.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit))
    shown = [PersonRow(**(dict(r._mapping) | {"providers": r.providers or []})) for r in rows]
    return PeoplePage(people=shown, total=total, offset=offset, limit=limit)
