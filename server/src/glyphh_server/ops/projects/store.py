"""An org's projects (docs/specs/bots.md, 10): made, read, changed and deleted on the request's transaction (the org
entered). A project's crew is the org's own bots, each once, in no order; its orchestrator is the org's orchestrator
bot, always (one given is not read); it runs on Glyphh cloud (runs_on none) or one of the org's rrotors (GET
/v1/bots/places). Its slug comes from its name and stays; a second of the same slug is refused."""

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Bot, Project
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import places
from glyphh_server.ops.bots.store import slugify
from glyphh_server.ops.projects.views import Member, ProjectIn, ProjectPatch, ProjectView

MISSING: str = "There is no such project."
FIELDS: frozenset[str] = frozenset(ProjectView.model_fields) - {"members", "github_connected"}
CLEARED: frozenset[str] = frozenset({"runs_on", "max_spend_cents"})  # null in a patch clears these


def repo(url: str) -> str:
    """`owner/name` of the project's https://github.com/<owner>/<name>."""
    return "/".join(url.rstrip("/").split("/")[-2:])


async def crew(conn: AsyncConnection, ids: list[str]) -> list[Any]:
    """The project's bots: those of them still the org's (in the order they were kept, which means nothing)."""
    found = {str(b.id): b for b in await conn.execute(select(Bot).where(Bot.id.in_([uuid.UUID(i) for i in ids])))}
    return [found[i] for i in ids if i in found]


async def _members(conn: AsyncConnection, given: list[uuid.UUID]) -> list[str]:
    ids = [str(i) for i in given]
    if len(set(ids)) != len(ids):
        raise Invalid("A bot is in a project's crew once.", reason="members")
    if missing := set(ids) - {str(b.id) for b in await crew(conn, ids)}:
        raise NotFound("The org has no such bot.", bot_ids=sorted(missing))
    return ids


async def _led(conn: AsyncConnection) -> uuid.UUID | None:
    """Who picks the next bot when a project's turns are the orchestrator's: the org's orchestrator bot, always
    (docs/specs/bot-agent-loop.md, 8). It is no longer chosen: an `orchestrator` given is not read."""
    return (await conn.execute(select(Bot.id).where(Bot.role == "orchestrator"))).scalar()


async def view(conn: AsyncConnection, project: Any) -> ProjectView:
    members = [Member(id=b.id, slug=b.slug, name=b.name) for b in await crew(conn, project.members)]
    connected = project.github_installation_id is not None
    return ProjectView(**{k: getattr(project, k) for k in FIELDS}, members=members, github_connected=connected)


async def row(conn: AsyncConnection, slug: str) -> Any:
    found = (await conn.execute(select(Project).where(Project.slug == slug))).first()
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return found


async def listing(conn: AsyncConnection) -> list[ProjectView]:
    return [await view(conn, p) for p in await conn.execute(select(Project).order_by(Project.name))]


async def one(conn: AsyncConnection, slug: str) -> ProjectView:
    return await view(conn, await row(conn, slug))


async def _saved(conn: AsyncConnection, statement: Any, slug: str) -> Any:
    try:
        async with conn.begin_nested():
            return (await conn.execute(statement.returning(Project))).one()
    except IntegrityError as err:
        raise Conflict(f"The org already has a project {slug!r}: name it another way.", slug=slug) from err


async def create(conn: AsyncConnection, who: Principal, body: ProjectIn, slug: str = "") -> ProjectView:
    slug = slug or slugify(body.name)
    members = await _members(conn, body.members)
    values: dict[str, Any] = {
        **body.model_dump(exclude={"members", "runs_on", "orchestrator"}),
        "orchestrator": await _led(conn),
        "repo_url": body.repo_url.rstrip("/"),
        "slug": slug,
        "members": members,
        "runs_on": await places.checked(conn, body.runs_on),
        "org_id": who.org_id,
        "created_by": who.user_id,
    }
    return await view(conn, await _saved(conn, Project.__table__.insert().values(**values), slug))


async def patch(conn: AsyncConnection, slug: str, body: ProjectPatch) -> ProjectView:
    project = await row(conn, slug)
    given = body.model_dump(exclude_unset=True, exclude={"orchestrator"})
    changes = {k: v for k, v in given.items() if v is not None or k in CLEARED} | {"orchestrator": await _led(conn)}
    if "members" in changes:
        changes["members"] = await _members(conn, body.members or [])
    if "runs_on" in changes:
        changes["runs_on"] = await places.checked(conn, changes["runs_on"])
    if "repo_url" in changes:
        changes["repo_url"] = changes["repo_url"].rstrip("/")
    if changes.get("repo_url", project.repo_url) != project.repo_url:
        changes["github_installation_id"] = None  # another repo: connected again by its next run
    statement = Project.__table__.update().where(Project.id == project.id).values(**changes, updated_at=func.now())
    return await view(conn, await _saved(conn, statement, slug))


async def remove(conn: AsyncConnection, slug: str) -> None:
    project = await row(conn, slug)
    await conn.execute(delete(Project).where(Project.id == project.id))
