"""The catalogue of org artifacts (docs/specs/artifacts.md, 3) as people see it: one row per app on an org's rrotor
(filled from the link, ops/catalogue.py; shown as ops/artifact_views.py), listed to a person by their roles (the
admin's or member's role, and the identity provider's groups), reviewed by the org's admin or a member of a reviewer
group (approve, reject, retire), each review told back down the runtime's link. The page itself never passes
through here: `url` is where it is, on the org's own rrotor."""

import logging
import uuid

from sqlalchemy import ColumnElement, Text, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Forbidden, NotFound
from glyphh_server.models import Artifact, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.artifact_views import ArtifactView, Page, app_url, query, view
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.catalogue import reviewer_groups, tell
from glyphh_server.ops.link.hub import Hub

log = logging.getLogger("glyphh.artifacts")

PER_PAGE: int = 24
PER_PAGE_MAX: int = 100
REASON_MAX: int = 500
STATES: tuple[str, ...] = ("draft", "approved", "rejected", "retired")
REVIEWERS_ONLY: str = "Only the org's reviewers see artifacts that are not approved."
MISSING: str = "No such artifact in your org."

__all__ = ["ArtifactView", "Page", "app_url"]


def roles_of(role: str, groups: list[str]) -> set[str]:
    return {role, *groups}


def allowed(roles: list[str], role: str, groups: list[str]) -> bool:
    """Whether an artifact's roles let this person in: none means everyone in the org."""
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
    return or_(func.cardinality(Artifact.roles) == 0, Artifact.roles.overlap(mine))


async def list_artifacts(
    conn: AsyncConnection,
    who: Principal,
    q: str | None = None,
    page: int = 1,
    per_page: int = PER_PAGE,
    state: str = "approved",
) -> Page:
    """A page of the org's artifacts, newest change first: the approved ones a member's roles allow; any other state
    (draft, rejected, retired) for reviewers only, every row."""
    role, groups, reviewer = await standing(conn, who)
    if state != "approved" and not reviewer:
        raise Forbidden(REVIEWERS_ONLY, reason="reviewer")
    where = [Artifact.org_id == who.org_id, Artifact.state == state]
    if not reviewer:
        where.append(_for(role, groups))
    if q:
        like = f"%{q.strip()}%"
        where.append(or_(Artifact.title.ilike(like), Artifact.description.ilike(like), Artifact.name.ilike(like)))
    total = (await conn.execute(select(func.count()).select_from(Artifact).where(*where))).scalar_one()
    rows = await conn.execute(
        query()
        .where(*where)
        .order_by(Artifact.updated_at.desc(), Artifact.id)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return Page(artifacts=[view(r) for r in rows], page=page, per_page=per_page, total=total)


async def _row(conn: AsyncConnection, who: Principal, artifact_id: uuid.UUID) -> Row:
    row = (await conn.execute(query().where(Artifact.id == artifact_id, Artifact.org_id == who.org_id))).first()
    if row is None:
        raise NotFound(MISSING, artifact_id=str(artifact_id))
    return row


async def get_artifact(conn: AsyncConnection, who: Principal, artifact_id: uuid.UUID) -> ArtifactView:
    """One, as it is listed to the caller: an approved one their roles allow, or any for a reviewer."""
    row = await _row(conn, who, artifact_id)
    role, groups, reviewer = await standing(conn, who)
    if not reviewer and not (row.state == "approved" and allowed(list(row.roles), role, groups)):
        raise NotFound(MISSING, artifact_id=str(artifact_id))
    return view(row)


async def _review(
    conn: AsyncConnection, hub: Hub, who: Principal, artifact_id: uuid.UUID, state: str, reason: str | None = None
) -> ArtifactView:
    row = await _row(conn, who, artifact_id)
    _, _, reviewer = await standing(conn, who)
    if not reviewer:
        raise Forbidden("Only the org's admin or a reviewer can review artifacts.", reason="reviewer")
    allowed_from = {"approved": ("draft", "rejected"), "rejected": ("draft", "approved"), "retired": STATES[:3]}
    if row.state not in allowed_from[state]:
        raise Conflict(f"{row.title} is {row.state}: it cannot be {state} from there.", state=row.state)
    await conn.execute(
        update(Artifact)
        .where(Artifact.id == artifact_id)
        .values(state=state, reviewed_by=who.user_id, reviewed_at=func.now(), reason=reason, updated_at=func.now())
    )
    log.info("artifact reviewed", extra=fields(artifact=str(artifact_id), state=state, by=str(who.user_id)))
    await tell(hub, row.runtime_id, row.name, row.version, state, list(row.roles))
    return view(await _row(conn, who, artifact_id))


async def approve(conn: AsyncConnection, hub: Hub, who: Principal, artifact_id: uuid.UUID) -> ArtifactView:
    return await _review(conn, hub, who, artifact_id, "approved")


async def reject(conn: AsyncConnection, hub: Hub, who: Principal, artifact_id: uuid.UUID, reason: str) -> ArtifactView:
    return await _review(conn, hub, who, artifact_id, "rejected", reason.strip())


async def retire(conn: AsyncConnection, hub: Hub, who: Principal, artifact_id: uuid.UUID) -> ArtifactView:
    return await _review(conn, hub, who, artifact_id, "retired")
