"""The catalogue of org apps (docs/specs/apps.md, 3) as people see it: one row per app on an org's rrotor (filled
from the link, ops/catalogue.py; shown as ops/app_views.py), listed to a person by their roles (the admin's or
member's role, and the identity provider's groups) and by type, reviewed by the org's admin or a member of a reviewer
group (approve, reject, retire), each review told back down the runtime's link. The files never pass through here:
`url` is where the app is, on the org's own rrotor."""

import logging
import uuid

from sqlalchemy import ColumnElement, Text, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Forbidden, NotFound
from glyphh_server.models import STATES, App, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.app_views import AppView, Page, app_url, query, view
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.catalogue import reviewer_groups, tell
from glyphh_server.ops.link.hub import Hub

log = logging.getLogger("glyphh.apps")

PER_PAGE: int = 24
PER_PAGE_MAX: int = 100
REASON_MAX: int = 500
REVIEWERS_ONLY: str = "Only the org's reviewers see apps that are not approved."
MISSING: str = "No such app in your org."

__all__ = ["AppView", "Page", "app_url"]


def roles_of(role: str, groups: list[str]) -> set[str]:
    return {role, *groups}


def allowed(roles: list[str], role: str, groups: list[str]) -> bool:
    """Whether an app's roles let this person in: none means everyone in the org."""
    return not roles or bool(set(roles) & roles_of(role, groups))


async def is_reviewer(conn: AsyncConnection, org_id: uuid.UUID, role: str, groups: list[str]) -> bool:
    """The org's admin, or a member of one of its reviewer groups (Settings → Auth)."""
    return role == "admin" or bool(set(groups) & set(await reviewer_groups(conn, org_id)))


async def standing(conn: AsyncConnection, who: Principal) -> tuple[str, list[str], bool]:
    """The caller's role, groups and whether they review."""
    groups = list((await conn.execute(select(User.groups).where(User.id == who.user_id))).scalar_one())
    return who.role, groups, await is_reviewer(conn, who.org_id, who.role, groups)


def _for(role: str, groups: list[str]) -> ColumnElement[bool]:
    """The rows whose roles let this person in."""
    mine = cast(sorted(roles_of(role, groups)), ARRAY(Text))
    return or_(func.cardinality(App.roles) == 0, App.roles.overlap(mine))


async def list_apps(
    conn: AsyncConnection,
    who: Principal,
    q: str | None = None,
    page: int = 1,
    per_page: int = PER_PAGE,
    state: str = "approved",
    type: str | None = None,
) -> Page:
    """A page of the org's apps, newest change first: the approved ones a member's roles allow; any other state
    (draft, rejected, retired) for reviewers only, every row. A `type` keeps only that type."""
    role, groups, reviewer = await standing(conn, who)
    if state != "approved" and not reviewer:
        raise Forbidden(REVIEWERS_ONLY, reason="reviewer")
    where = [App.org_id == who.org_id, App.state == state]
    if not reviewer:
        where.append(_for(role, groups))
    if type:
        where.append(App.type == type)
    if q:
        like = f"%{q.strip()}%"
        where.append(or_(App.title.ilike(like), App.description.ilike(like), App.name.ilike(like)))
    total = (await conn.execute(select(func.count()).select_from(App).where(*where))).scalar_one()
    rows = await conn.execute(
        query().where(*where).order_by(App.updated_at.desc(), App.id).offset((page - 1) * per_page).limit(per_page)
    )
    return Page(apps=[view(r) for r in rows], page=page, per_page=per_page, total=total)


async def _row(conn: AsyncConnection, who: Principal, app_id: uuid.UUID) -> Row:
    row = (await conn.execute(query().where(App.id == app_id, App.org_id == who.org_id))).first()
    if row is None:
        raise NotFound(MISSING, app_id=str(app_id))
    return row


async def get_app(conn: AsyncConnection, who: Principal, app_id: uuid.UUID) -> AppView:
    """One, as it is listed to the caller: an approved one their roles allow, or any for a reviewer."""
    row = await _row(conn, who, app_id)
    role, groups, reviewer = await standing(conn, who)
    if not reviewer and not (row.state == "approved" and allowed(list(row.roles), role, groups)):
        raise NotFound(MISSING, app_id=str(app_id))
    return view(row)


async def _review(
    conn: AsyncConnection, hub: Hub, who: Principal, app_id: uuid.UUID, state: str, reason: str | None = None
) -> AppView:
    row = await _row(conn, who, app_id)
    _, _, reviewer = await standing(conn, who)
    if not reviewer:
        raise Forbidden("Only the org's admin or a reviewer can review apps.", reason="reviewer")
    allowed_from = {"approved": ("draft", "rejected"), "rejected": ("draft", "approved"), "retired": STATES[:3]}
    if row.state not in allowed_from[state]:
        raise Conflict(f"{row.title} is {row.state}: it cannot be {state} from there.", state=row.state)
    await conn.execute(
        update(App)
        .where(App.id == app_id)
        .values(state=state, reviewed_by=who.user_id, reviewed_at=func.now(), reason=reason, updated_at=func.now())
    )
    log.info("app reviewed", extra=fields(app=str(app_id), state=state, by=str(who.user_id)))
    await tell(hub, row.runtime_id, row.name, row.version, state, list(row.roles))
    return view(await _row(conn, who, app_id))


async def approve(conn: AsyncConnection, hub: Hub, who: Principal, app_id: uuid.UUID) -> AppView:
    return await _review(conn, hub, who, app_id, "approved")


async def reject(conn: AsyncConnection, hub: Hub, who: Principal, app_id: uuid.UUID, reason: str) -> AppView:
    return await _review(conn, hub, who, app_id, "rejected", reason.strip())


async def retire(conn: AsyncConnection, hub: Hub, who: Principal, app_id: uuid.UUID) -> AppView:
    return await _review(conn, hub, who, app_id, "retired")
