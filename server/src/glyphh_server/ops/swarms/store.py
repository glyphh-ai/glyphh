"""An org's swarms (docs/specs/bots.md, 10): made, read, changed and deleted on the request's transaction (the org
entered). A swarm's crew is the org's own bots, each once, in speaking order; it runs on one of the org's rrotors
(GET /v1/bots/places), never on Glyphh cloud. Its slug comes from its name and stays; a second of the same slug is
refused."""

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Bot, Swarm
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import places
from glyphh_server.ops.bots.store import slugify
from glyphh_server.ops.swarms.views import Member, SwarmIn, SwarmPatch, SwarmView

MISSING: str = "There is no such swarm."
FIELDS: tuple[str, ...] = ("id", "slug", "name", "repo_url", "base_branch", "rounds", "review", "runs_on")


def repo(url: str) -> str:
    """`owner/name` of the swarm's https://github.com/<owner>/<name>."""
    return "/".join(url.rstrip("/").split("/")[-2:])


async def crew(conn: AsyncConnection, ids: list[str]) -> list[Any]:
    """The swarm's bots, in its order: those of them still the org's."""
    found = {str(b.id): b for b in await conn.execute(select(Bot).where(Bot.id.in_([uuid.UUID(i) for i in ids])))}
    return [found[i] for i in ids if i in found]


async def _members(conn: AsyncConnection, given: list[uuid.UUID]) -> list[str]:
    ids = [str(i) for i in given]
    if len(set(ids)) != len(ids):
        raise Invalid("A bot is in a swarm's crew once.", reason="members")
    if missing := set(ids) - {str(b.id) for b in await crew(conn, ids)}:
        raise NotFound("The org has no such bot.", bot_ids=sorted(missing))
    return ids


async def _place(conn: AsyncConnection, runs_on: uuid.UUID) -> uuid.UUID:
    checked = await places.checked(conn, runs_on)
    assert checked is not None
    return checked


async def view(conn: AsyncConnection, swarm: Any) -> SwarmView:
    members = [Member(id=b.id, slug=b.slug, name=b.name) for b in await crew(conn, swarm.members)]
    fields = {k: getattr(swarm, k) for k in FIELDS}
    return SwarmView(**fields, members=members, created_at=swarm.created_at, updated_at=swarm.updated_at)


async def row(conn: AsyncConnection, slug: str) -> Any:
    found = (await conn.execute(select(Swarm).where(Swarm.slug == slug))).first()
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return found


async def listing(conn: AsyncConnection) -> list[SwarmView]:
    return [await view(conn, s) for s in await conn.execute(select(Swarm).order_by(Swarm.name))]


async def one(conn: AsyncConnection, slug: str) -> SwarmView:
    return await view(conn, await row(conn, slug))


async def _saved(conn: AsyncConnection, statement: Any, slug: str) -> Any:
    try:
        async with conn.begin_nested():
            return (await conn.execute(statement.returning(Swarm))).one()
    except IntegrityError as err:
        raise Conflict(f"The org already has a swarm {slug!r}: name it another way.", slug=slug) from err


async def create(conn: AsyncConnection, who: Principal, body: SwarmIn) -> SwarmView:
    slug = slugify(body.name)
    values: dict[str, Any] = {
        **body.model_dump(exclude={"members", "runs_on"}),
        "repo_url": body.repo_url.rstrip("/"),
        "slug": slug,
        "members": await _members(conn, body.members),
        "runs_on": await _place(conn, body.runs_on),
        "org_id": who.org_id,
        "created_by": who.user_id,
    }
    return await view(conn, await _saved(conn, Swarm.__table__.insert().values(**values), slug))


async def patch(conn: AsyncConnection, slug: str, body: SwarmPatch) -> SwarmView:
    swarm = await row(conn, slug)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "members" in changes:
        changes["members"] = await _members(conn, body.members or [])
    if "runs_on" in changes:
        changes["runs_on"] = await _place(conn, changes["runs_on"])
    if "repo_url" in changes:
        changes["repo_url"] = changes["repo_url"].rstrip("/")
    statement = Swarm.__table__.update().where(Swarm.id == swarm.id).values(**changes, updated_at=func.now())
    return await view(conn, await _saved(conn, statement, slug))


async def remove(conn: AsyncConnection, slug: str) -> None:
    swarm = await row(conn, slug)
    await conn.execute(delete(Swarm).where(Swarm.id == swarm.id))
