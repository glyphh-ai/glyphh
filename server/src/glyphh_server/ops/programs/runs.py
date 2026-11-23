"""A program's runs, as rows: made, changed and read, each on its own transaction in the run's org. A run started
while its program's last run is still live is refused; a run cut off by its machine stopping is failed when that
machine starts again."""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Program, ProgramRun
from glyphh_server.ops.bots.runs import machine, now
from glyphh_server.ops.programs.views import ProgramRunView

LIVE_ALREADY: str = "{name} is already running: answer its question, or cancel it, first."
MISSING: str = "There is no such program run."
CUT: str = "The server restarted while it ran: run it again."


def view(run: Any, slug: str = "") -> ProgramRunView:
    return ProgramRunView(
        id=run.id, program=slug or run.program_slug, status=run.status, trigger=run.trigger, input=run.input, at=run.at,
        outputs={k: v for k, v in run.outputs.items() if not k.startswith("_")}, question=run.question or None,
        error=run.error, created_at=run.created_at, started_at=run.started_at, finished_at=run.finished_at,
    )  # fmt: skip


async def create(engine: AsyncEngine, program: Any, user_id: Any, trigger: str, given: str, first: str) -> Any:
    async with engine.begin() as conn:
        await tenancy.enter(conn, program.org_id)
        values = {"org_id": program.org_id, "program_id": program.id, "user_id": user_id, "trigger": trigger,
                  "input": given, "at": first}  # fmt: skip
        try:
            async with conn.begin_nested():
                return (await conn.execute(ProgramRun.__table__.insert().values(**values).returning(ProgramRun))).one()
        except IntegrityError as err:
            raise Conflict(LIVE_ALREADY.format(name=program.name), slug=program.slug) from err


async def put(
    engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, when: str | None = None, **values: Any
) -> bool:
    """The run's row changed (only while its status is `when`, when given): whether it was."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        where = [ProgramRun.id == run_id] + ([ProgramRun.status == when] if when else [])
        return (await conn.execute(update(ProgramRun).where(*where).values(**values))).rowcount == 1


async def row(conn: AsyncConnection, run_id: uuid.UUID) -> Any:
    """The run's row, with its program's slug (`program_slug`)."""
    named = select(ProgramRun, Program.slug.label("program_slug")).join(Program, Program.id == ProgramRun.program_id)
    found = (await conn.execute(named.where(ProgramRun.id == run_id))).one_or_none()
    if found is None:
        raise NotFound(MISSING, run_id=str(run_id))
    return found


async def shown(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID) -> ProgramRunView:
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        return view(await row(conn, run_id))


async def listed(conn: AsyncConnection, program: Any, limit: int = 50) -> list[ProgramRunView]:
    query = (
        select(ProgramRun)
        .where(ProgramRun.program_id == program.id)
        .order_by(ProgramRun.created_at.desc())
        .limit(limit)
    )
    return [view(r, program.slug) for r in (await conn.execute(query)).all()]


async def ended(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, status: str, error: str = "") -> bool:
    """The run over: done, or failed saying why (only while it is still live)."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        live = ProgramRun.status.in_(("queued", "running", "dispatched", "needs_input"))
        done = {"status": status, "error": error, "question": {}, "finished_at": now()}
        return (
            await conn.execute(update(ProgramRun).where(ProgramRun.id == run_id, live).values(**done))
        ).rowcount == 1


async def recover(engine: AsyncEngine) -> list[Any]:
    """The runs this machine was walking when it stopped, failed (no org is entered): them."""
    async with engine.begin() as conn:
        cut = (
            update(ProgramRun)
            .where(ProgramRun.machine == machine(), ProgramRun.status.in_(("queued", "running")))
            .values(status="failed", error=CUT, finished_at=now())
        )
        return list((await conn.execute(cut.returning(ProgramRun.id, ProgramRun.org_id))).all())
