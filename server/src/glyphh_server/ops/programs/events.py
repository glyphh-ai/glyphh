"""A program run's audit trail (docs/specs/programs.md, 4): one line for each thing that happened, append only, in
order: who or what started it, each step (which bot did it, whether it worked, in plain words), each question and
who answered it, and how it ended. Never what a tool answered: that is the run's own."""

import uuid
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Bot, ProgramEvent, User
from glyphh_server.ops.programs.views import EventView

DETAIL_MAX: int = 500
PAGE: int = 500


async def note(
    engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, kind: str, step: str = "", **more: Any
) -> None:
    """One line: `kind`, at `step`; `more`: title, bot_id, user_id, ok, detail."""
    more["detail"] = str(more.get("detail") or "")[:DETAIL_MAX]
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        await conn.execute(insert(ProgramEvent).values(org_id=org_id, run_id=run_id, kind=kind, step=step, **more))


async def read(conn: AsyncConnection, run_id: uuid.UUID, after: int = 0) -> list[EventView]:
    """The run's lines after `after` (a line's `n`), oldest first; the bot by its slug and the person by name."""
    e = ProgramEvent
    who = func.coalesce(User.name, User.email).label("by")
    query = (
        select(e.id, e.at, e.kind, e.step, e.title, e.ok, e.detail, Bot.slug.label("bot"), who)
        .outerjoin(Bot, Bot.id == ProgramEvent.bot_id)
        .outerjoin(User, User.id == ProgramEvent.user_id)
        .where(ProgramEvent.run_id == run_id, ProgramEvent.id > after)
        .order_by(ProgramEvent.id)
        .limit(PAGE)
    )
    return [
        EventView(
            n=r.id, at=r.at, kind=r.kind, step=r.step, title=r.title, bot=r.bot, by=r.by, ok=r.ok, detail=r.detail
        )
        for r in (await conn.execute(query)).all()
    ]
