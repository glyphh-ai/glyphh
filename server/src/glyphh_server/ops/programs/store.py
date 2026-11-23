"""An org's programs: made, read, changed and deleted on the request's transaction (the org entered). A program is
its `program.py` (ops/programs/flow.py): saving its steps writes them into the file, saving the file replaces it, and
either way its view reads the steps back from the file. A program whose steps cannot run is kept all the same, its
problems said (a canvas half drawn is saved); it is refused only when it is run."""

import re
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Bot, Program, ProgramRun
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import places, schedule
from glyphh_server.ops.programs import flow
from glyphh_server.ops.programs.views import ProgramIn, ProgramPatch, ProgramView

MISSING: str = "There is no such program."
BOTH: str = "Save its steps or its file, not both at once."
NO_BOT: str = "There is no bot {slug!r}."
CODE_ON_CLOUD: str = (
    "{step}: code does not run on Glyphh cloud yet: choose one of your rrotors for this program, and its code runs "
    "there"
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = re.sub(r"^[^a-z]+", "", slug)[:40].strip("-")
    if not slug:
        raise Invalid("A program's name needs a letter.", reason="name")
    return slug


def source_of(source: str | None, steps: list[dict[str, Any]] | None, was: str = flow.EMPTY) -> str:
    """The file to keep: the one given, or the one it was with these steps written in."""
    if source is not None and steps is not None:
        raise Invalid(BOTH, reason="source")
    if source is not None:
        return source
    if steps is None:
        return was
    try:
        return flow.write(was, steps)
    except SyntaxError:  # the file it was cannot be read: the steps start a new one
        return flow.write(flow.EMPTY, steps)


def parsed(source: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Its steps, its functions and its problems (a file that cannot be read has no steps and says why)."""
    try:
        steps, functions = flow.read(source)
    except flow.Bad as err:
        return [], [], [str(err)]
    return steps, functions, flow.check(steps, functions)


def can_run_on(steps: list[dict[str, Any]]) -> list[str]:
    return ["rrotor"] if any(s.get("kind") == "code" for s in steps) else ["cloud", "rrotor"]


async def _bot_of(conn: AsyncConnection, slug: str | None) -> uuid.UUID | None:
    if not slug:
        return None
    found = (await conn.execute(select(Bot.id).where(Bot.slug == slug))).scalar_one_or_none()
    if found is None:
        raise NotFound(NO_BOT.format(slug=slug), bot=slug)
    return found


async def _bots(conn: AsyncConnection, steps: list[dict[str, Any]]) -> list[str]:
    named = {s["bot"] for s in steps if isinstance(s.get("bot"), str)}
    if not named:
        return []
    have = set((await conn.scalars(select(Bot.slug).where(Bot.slug.in_(named)))).all())
    return [f"{s['id']}: there is no bot {s['bot']}" for s in steps if s.get("bot") in named - have]


async def view(conn: AsyncConnection, program: Any) -> ProgramView:
    steps, functions, problems = parsed(program.source)
    problems += await _bots(conn, steps) if not problems else []
    places_ok = can_run_on(steps)
    if program.runs_on is None and "cloud" not in places_ok:
        problems += [CODE_ON_CLOUD.format(step=s["id"]) for s in steps if s.get("kind") == "code"]
    bot = (await conn.execute(select(Bot.slug).where(Bot.id == program.bot_id))).scalar_one_or_none()
    last = (
        await conn.execute(
            select(ProgramRun).where(ProgramRun.program_id == program.id).order_by(ProgramRun.created_at.desc())
        )
    ).first()
    return ProgramView(
        id=program.id, slug=program.slug, name=program.name, summary=program.summary, bot=bot, source=program.source,
        flow=steps, functions=functions, problems=problems, can_run_on=places_ok, template=program.template,
        last_run={"id": str(last.id), "status": last.status, "created_at": last.created_at.isoformat()}
        if last else None,
        created_at=program.created_at, updated_at=program.updated_at, **schedule.shown(program),
    )  # fmt: skip


async def row(conn: AsyncConnection, slug: str) -> Any:
    found = (await conn.execute(select(Program).where(Program.slug == slug))).one_or_none()
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return found


async def _saved(conn: AsyncConnection, statement: Any, slug: str) -> Any:
    try:
        async with conn.begin_nested():
            return (await conn.execute(statement.returning(Program))).one()
    except IntegrityError as err:
        raise Conflict(f"The org already has a program {slug!r}: name it another way.", slug=slug) from err


async def made(conn: AsyncConnection, who: Principal, body: ProgramIn, template: str = "") -> Any:
    slug = slugify(body.name)
    values = {
        "org_id": who.org_id, "created_by": who.user_id, "slug": slug, "name": body.name, "summary": body.summary,
        "bot_id": await _bot_of(conn, body.bot), "source": source_of(body.source, body.flow), "template": template,
        "runs_on": await places.checked(conn, body.runs_on), "schedule": body.schedule.model_dump(),
        "next_run_at": schedule.next_after(body.schedule, schedule.now()),
    }  # fmt: skip
    return await _saved(conn, Program.__table__.insert().values(**values), slug)


async def create(conn: AsyncConnection, who: Principal, body: ProgramIn) -> ProgramView:
    return await view(conn, await made(conn, who, body))


async def patch(conn: AsyncConnection, slug: str, body: ProgramPatch) -> ProgramView:
    program = await row(conn, slug)
    given = body.model_fields_set
    changes: dict[str, Any] = {k: getattr(body, k) for k in ("name", "summary") if getattr(body, k) is not None}
    if "source" in given or "flow" in given:
        changes["source"] = source_of(body.source, body.flow, program.source)
    if "bot" in given:
        changes["bot_id"] = await _bot_of(conn, body.bot)
    if "runs_on" in given:  # null is Glyphh cloud again
        changes["runs_on"] = await places.checked(conn, body.runs_on)
    if body.schedule is not None:  # its next run worked out again, from now
        then = schedule.next_after(body.schedule, schedule.now())
        changes |= {"schedule": body.schedule.model_dump(), "next_run_at": then}
    statement = Program.__table__.update().where(Program.id == program.id).values(**changes, updated_at=func.now())
    return await view(conn, await _saved(conn, statement, program.slug))


async def remove(conn: AsyncConnection, slug: str) -> None:
    program = await row(conn, slug)
    await conn.execute(delete(Program).where(Program.id == program.id))


async def listed(conn: AsyncConnection, q: str = "") -> list[ProgramView]:
    query = select(Program).order_by(Program.name)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.where(Program.name.ilike(like) | Program.summary.ilike(like) | Program.slug.ilike(like))
    return [await view(conn, p) for p in (await conn.execute(query)).all()]
