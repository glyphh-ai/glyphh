"""Recents (docs/specs/bots.md, 11): the org's runs in one list, a bot's own and a crew's (a project's) alike, the
newest first: the task's first line, who ran it, when, how it stands, whether it waits on a person, and for a crew's
its workspace (the repo and branch). Searched, filtered (waiting, pinned, archived) and paged by a cursor. Each
person pins and archives runs for themselves (run_marks); a run deleted is deleted for the org, once it has ended.
`needs_you` counts the org's runs that wait on a person now: the bots' questions and the crews' pull requests."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, false, func, literal, null, or_, select, union_all
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Bot, BotRun, Project, ProjectRun, RunMark
from glyphh_server.models.bot import LIVE
from glyphh_server.ops.auth.principal import Principal

WAITS: str = "needs_input"
TITLE_MAX: int = 120
CREW: str = "Crew"
MISSING: str = "There is no such run."
STILL_LIVE: str = "That run is still going or waiting: cancel it first."
Mark = Literal["pin", "unpin", "archive", "unarchive"]
MARKS: dict[str, dict[str, bool]] = {
    "pin": {"pinned": True},
    "unpin": {"pinned": False},
    "archive": {"archived": True},
    "unarchive": {"archived": False},
}


class Recent(BaseModel):
    id: uuid.UUID
    kind: Literal["bot", "crew"]
    title: str = Field(description="The task's first line; empty when the run was given none")
    bot_slug: str | None = Field(description="A bot's run: its bot")
    bot_name: str = Field(description="A bot's run: its bot's name; a crew's: Crew")
    project_slug: str | None = Field(description="A crew's run: its project")
    workspace: str | None = Field(description="A crew's run: its GitHub repo, owner/name")
    branch: str | None = Field(description="A crew's run: its workspace's branch")
    runs_on: uuid.UUID | None = Field(description="The rrotor it ran on; none: Glyphh cloud")
    status: str
    waiting: bool = Field(description="It waits on a person")
    pinned: bool
    archived: bool
    created_at: datetime


class Recents(BaseModel):
    recents: list[Recent]
    next_cursor: datetime | None = Field(description="Pass as `cursor` for the next page; none: no more")
    needs_you: int = Field(description="The org's runs that wait on a person now, whatever the filters")
    archived_count: int = Field(description="The runs this person archived")


class Asked(BaseModel):
    """What a recents read asks for."""

    q: str = ""
    waiting: bool = False
    archived: bool = False
    pinned: bool = False
    cursor: datetime | None = None
    limit: int = 30


def _runs() -> Any:
    """Every run of the org, a bot's or a crew's, in one shape."""
    none = null()
    bots = select(
        BotRun.id,
        literal("bot").label("kind"),
        BotRun.input.label("task"),
        Bot.slug.label("bot_slug"),
        Bot.name.label("bot_name"),
        none.label("project_slug"),
        none.label("repo_url"),
        none.label("branch"),
        BotRun.rrotor_id.label("runs_on"),
        BotRun.status,
        BotRun.created_at,
    ).join(Bot, Bot.id == BotRun.bot_id)
    crews = select(
        ProjectRun.id,
        literal("crew"),
        ProjectRun.task,
        none,
        literal(CREW),
        Project.slug,
        Project.repo_url,
        Project.base_branch,
        ProjectRun.rrotor_id,
        ProjectRun.status,
        ProjectRun.created_at,
    ).join(Project, Project.id == ProjectRun.project_id)
    return union_all(bots, crews).subquery("runs")


def _marked(runs: Any, user_id: uuid.UUID) -> Any:
    """The runs with this person's marks beside them (none: neither pinned nor archived)."""
    mine = and_(RunMark.run_id == runs.c.id, RunMark.user_id == user_id)
    pinned = func.coalesce(RunMark.pinned, false()).label("pinned")
    archived = func.coalesce(RunMark.archived, false()).label("archived")
    return select(runs, pinned, archived).select_from(runs.outerjoin(RunMark, mine)), pinned, archived


def _recent(r: Any) -> Recent:
    lines = [line.strip() for line in r.task.splitlines() if line.strip()]
    workspace = "/".join(r.repo_url.split("/")[-2:]) if r.repo_url else None
    fields = {k: getattr(r, k) for k in ("id", "kind", "bot_slug", "bot_name", "project_slug", "branch", "runs_on")}
    fields |= {"status": r.status, "pinned": r.pinned, "archived": r.archived, "created_at": r.created_at}
    return Recent(**fields, title=(lines or [""])[0][:TITLE_MAX], workspace=workspace, waiting=r.status == WAITS)


async def listing(conn: AsyncConnection, who: Principal, asked: Asked) -> Recents:
    runs = _runs()
    found, pinned, archived = _marked(runs, who.user_id)
    found = found.where(archived == asked.archived)
    if asked.waiting:
        found = found.where(runs.c.status == WAITS)
    if asked.pinned:
        found = found.where(pinned)
    if asked.q.strip():
        like = f"%{asked.q.strip()}%"
        found = found.where(or_(runs.c.task.ilike(like), runs.c.bot_name.ilike(like), runs.c.repo_url.ilike(like)))
    if asked.cursor is not None:
        found = found.where(runs.c.created_at < asked.cursor)
    rows = list(await conn.execute(found.order_by(runs.c.created_at.desc(), runs.c.id).limit(asked.limit + 1)))
    shown = [_recent(r) for r in rows[: asked.limit]]
    waits = select(func.count()).select_from(runs).where(runs.c.status == WAITS)
    hidden = (
        select(func.count())
        .select_from(runs.join(RunMark, RunMark.run_id == runs.c.id))
        .where(RunMark.user_id == who.user_id, RunMark.archived)
    )
    return Recents(
        recents=shown,
        next_cursor=shown[-1].created_at if len(rows) > asked.limit else None,
        needs_you=(await conn.execute(waits)).scalar_one(),
        archived_count=(await conn.execute(hidden)).scalar_one(),
    )


async def one(conn: AsyncConnection, who: Principal, run_id: uuid.UUID) -> Recent:
    runs = _runs()
    found = (await conn.execute(_marked(runs, who.user_id)[0].where(runs.c.id == run_id))).first()
    if found is None:
        raise NotFound(MISSING, run_id=str(run_id))
    return _recent(found)


async def mark(conn: AsyncConnection, who: Principal, run_id: uuid.UUID, how: Mark) -> Recent:
    """The person's own pin or archive on a run, set or lifted."""
    await one(conn, who, run_id)
    values = {"user_id": who.user_id, "run_id": run_id, "org_id": who.org_id, **MARKS[how]}
    kept = insert(RunMark).values(**values)
    await conn.execute(kept.on_conflict_do_update(index_elements=[RunMark.user_id, RunMark.run_id], set_=MARKS[how]))
    return await one(conn, who, run_id)


async def remove(conn: AsyncConnection, who: Principal, run_id: uuid.UUID) -> None:
    """The run deleted for the org, with its turns and everyone's marks on it; refused while it is live."""
    found = await one(conn, who, run_id)
    if found.status in LIVE:
        raise Conflict(STILL_LIVE, reason="run_live", run_id=str(run_id))
    table = BotRun if found.kind == "bot" else ProjectRun
    await conn.execute(delete(table).where(table.id == run_id))
    await conn.execute(delete(RunMark).where(RunMark.run_id == run_id))
