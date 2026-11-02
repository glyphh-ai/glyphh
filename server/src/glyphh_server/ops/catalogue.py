"""The catalogue's side of the link (docs/specs/apps.md, 3.2 and 3.4): a rrotor's `deployed` whose manifest is an
app makes or updates its row as a draft; every review is told back down the runtime's link as an `app` message (the
link says it in the runtime's own protocol, ops/link/hub.py); a welcome carries every row of the runtime and the org's
reviewer groups. The reviewers themselves (ops/sso.py's `reviewers`, Settings → Auth) are read here too, so the
roles check (ops/apps.py) and the welcome share one reader."""

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import TYPES, App, OrgSso, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import AppState, Deployed

log = logging.getLogger("glyphh.apps")

TITLE_MAX: int = 200
DESCRIPTION_MAX: int = 2000
ROLES_MAX: int = 50
ROLE_LEN: int = 120


async def reviewer_groups(conn: AsyncConnection, org_id: uuid.UUID) -> list[str]:
    """The groups that review the org's apps beside its admin; none without single sign-on."""
    found = (await conn.execute(select(OrgSso.reviewers).where(OrgSso.org_id == org_id))).scalar_one_or_none()
    return list(found or [])


async def tell(hub: Hub, runtime_id: uuid.UUID, program: str, version: int, state: str, roles: list[str]) -> bool:
    """The app's state down the runtime's link; False when no process holds it (its next welcome carries it)."""
    message = AppState(program=program, version=version, state=state, roles=roles)
    sent = await hub.deliver(runtime_id, message)
    if not sent:
        log.info("app state waits for the runtime's next welcome", extra=fields(runtime=str(runtime_id)))
    return sent


def subject_of(value: str | None) -> uuid.UUID | None:
    """The Glyphh subject a `deployed` names, when it is one."""
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def roles_in(app: dict[str, Any]) -> list[str]:
    """An app's `roles`, cleaned: strings, lower-cased, trimmed, capped."""
    given = app.get("roles")
    if not isinstance(given, list):
        return []
    roles = [r.strip().lower()[:ROLE_LEN] for r in given if isinstance(r, str) and r.strip()]
    return list(dict.fromkeys(roles))[:ROLES_MAX]


def type_of(app: dict[str, Any]) -> str:
    """An app's `type`, one of the six; anything else (or none) is a page."""
    given = app.get("type")
    return given if given in TYPES else "page"


async def catalogue_deployed(conn: AsyncConnection, runtime: Runtime, message: Deployed) -> bool:
    """A rrotor's `deployed` whose manifest is an app makes or updates the catalogue row, as a draft: the title from
    `app.title` (else the name), the description from the manifest's, the type from `app.type` (else page), the roles
    from `app.roles`, submitted by the Glyphh subject the message names when they are the org's. Any other deploy
    changes nothing (False)."""
    manifest = message.manifest if isinstance(message.manifest, dict) else {}
    if manifest.get("kind") != "app":
        return False
    app: dict[str, Any] = manifest.get("app") if isinstance(manifest.get("app"), dict) else {}
    by = subject_of(message.by)
    if by is not None:
        found = select(User.id).where(User.id == by, User.org_id == runtime.org_id)
        by = (await conn.execute(found)).scalar_one_or_none()
    values = {
        "title": str(app.get("title") or message.program)[:TITLE_MAX],
        "description": str(manifest.get("description") or "")[:DESCRIPTION_MAX],
        "type": type_of(app),
        "version": message.version,
        "commit_sha": message.commit_sha,
        "roles": roles_in(app),
        "state": "draft",
        "submitted_by": by,
        "submitted_at": func.now(),
        "reviewed_by": None,
        "reviewed_at": None,
        "reason": None,
        "updated_at": func.now(),
    }
    await conn.execute(
        upsert(App)
        .values(org_id=runtime.org_id, runtime_id=runtime.id, name=message.program, **values)
        .on_conflict_do_update(index_elements=["runtime_id", "name"], set_=values)
    )
    log.info("app catalogued", extra=fields(runtime=str(runtime.id), program=message.program))
    return True


async def for_runtime(conn: AsyncConnection, runtime_id: uuid.UUID) -> list[AppState]:
    """Every row of the runtime, for its welcome."""
    rows = await conn.execute(
        select(App.name, App.version, App.state, App.roles).where(App.runtime_id == runtime_id).order_by(App.name)
    )
    return [AppState(program=r.name, version=r.version, state=r.state, roles=list(r.roles)) for r in rows]
