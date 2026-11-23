"""A bot's runs in the database: made queued (a bot has one live run at a time: queued, running, dispatched to its
rrotor, or waiting on the person), started, and left by its turn (ops/bots/agent/run.py) done, failed, or
needs_input with the question it waits on (answered, the same run is queued again and its session carried on); a run
past its bot's runs a day is skipped. A run records the machine running it: when that machine starts again, its runs
still queued or running were cut off, and are failed; a run on a rrotor is the rrotor's, never cut off by a restart
here."""

import os
import socket
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Bot, BotRun, BotSession
from glyphh_server.ops.bots import files, said, shown
from glyphh_server.ops.bots.runs_words import INTERRUPTED
from glyphh_server.ops.bots.views import Question, RunView

MISSING: str = "There is no such run."
LIVE: str = "The bot has a run going or waiting on an answer: answer it, or cancel it, first."
SHOWN: int = 50
BOT = (Bot.slug,)  # a run read with its bot's slug
TOLD: frozenset[str] = frozenset(
    {"bot_slug", "question", "runs_on", "kind", "project_slug", "data", *shown.Shown.model_fields}
)


def machine() -> str:
    return os.environ.get("FLY_MACHINE_ID") or socket.gethostname()


def now() -> datetime:
    return datetime.now(UTC)


def view(run: Any, slug: str) -> RunView:
    """The run as it is shown: its record, and what it says of itself (a plain sentence when it has no words of its
    own, what it used, the pages and MCP Apps its tools brought back, the files it touched)."""
    asked = Question(**run.question) if run.question else None
    back = {"links": shown.links(run), "apps": shown.apps(run), "files": files.of(run), "steps": shown.steps(run)}
    kept = {k: getattr(run, k) for k in RunView.model_fields.keys() - TOLD}
    made = {k: v for k, v in (run.data or {}).items() if not k.startswith("_")}  # what its actions answered
    return RunView(
        bot_slug=slug, question=asked, runs_on=run.rrotor_id, summary=said.summary(run), data=made, **back, **kept
    )


def joined(found: Any) -> RunView:
    """A run read with its bot (BOT)."""
    return view(found, found.slug)


def of(run: Any, bot: Any) -> RunView:
    return view(run, bot.slug)


async def row(conn: AsyncConnection, run_id: uuid.UUID) -> Any:
    found = (
        await conn.execute(select(BotRun, *BOT).join(Bot, Bot.id == BotRun.bot_id).where(BotRun.id == run_id))
    ).first()
    if found is None:
        raise NotFound(MISSING, run_id=str(run_id))
    return found


async def get(conn: AsyncConnection, run_id: uuid.UUID) -> RunView:
    return joined(await row(conn, run_id))


async def listing(conn: AsyncConnection, bot: Any) -> list[RunView]:
    newest = select(BotRun).where(BotRun.bot_id == bot.id).order_by(BotRun.created_at.desc()).limit(SHOWN)
    return [of(r, bot) for r in await conn.execute(newest)]


async def waiting(conn: AsyncConnection) -> list[RunView]:
    """The org's runs waiting on the person (its approvals queue), oldest first: what each asks."""
    asked = (
        select(BotRun, *BOT)
        .join(Bot, Bot.id == BotRun.bot_id)
        .where(BotRun.status == "needs_input")
        .order_by(BotRun.created_at)
        .limit(SHOWN)
    )
    return [joined(r) for r in await conn.execute(asked)]


async def create(engine: AsyncEngine, org_id: uuid.UUID, bot: Any, user_id: uuid.UUID | None, given: str) -> RunView:
    """The run, queued and committed, so its task finds it; refused while the bot has a live run."""
    try:
        async with engine.begin() as conn:
            await tenancy.enter(conn, org_id)
            values = {"org_id": org_id, "bot_id": bot.id, "user_id": user_id, "input": given, "machine": machine()}
            made = (await conn.execute(BotRun.__table__.insert().values(**values).returning(BotRun))).one()
    except IntegrityError as err:
        raise Conflict(LIVE, slug=bot.slug) from err
    return of(made, bot)


async def today(engine: AsyncEngine, bot: Any) -> int:
    """How many runs of the bot were made since midnight (UTC)."""
    since = now().replace(hour=0, minute=0, second=0, microsecond=0)
    async with engine.begin() as conn:
        await tenancy.enter(conn, bot.org_id)
        made = select(func.count()).select_from(BotRun).where(BotRun.bot_id == bot.id, BotRun.created_at >= since)
        return int((await conn.execute(made)).scalar_one())


async def parent(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID) -> Any:
    """The orchestrator's run that waits on this run (a bot it asked), when this run no longer waits itself."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        mine = (await conn.execute(select(BotRun.status).where(BotRun.id == run_id))).scalar_one()
        if mine == "needs_input":
            return None
        waits = (BotRun.status == "needs_input", BotRun.question["child_run"].astext == str(run_id))
        return (await conn.execute(select(BotRun).where(*waits))).first()


async def put(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, **values: Any) -> None:
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        await conn.execute(update(BotRun).where(BotRun.id == run_id).values(**values))


async def queue(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    """A run that waited on the person, queued again to carry on; False when it no longer waits."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        again = (
            update(BotRun)
            .where(BotRun.id == run_id, BotRun.status == "needs_input")
            .values(status="queued", question={}, machine=machine())
        )
        return (await conn.execute(again)).rowcount == 1


async def start(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, own_key: bool) -> None:
    started = func.coalesce(BotRun.started_at, func.now())
    await put(engine, org_id, run_id, status="running", started_at=started, own_key=own_key)


async def failed(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, error: str) -> None:
    await put(engine, org_id, run_id, status="failed", error=error, question={}, finished_at=now(), session_id="")


async def skipped(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, why: str) -> None:
    await put(engine, org_id, run_id, status="skipped", error=why, finished_at=now())


async def recover(engine: AsyncEngine, here: str) -> int:
    """This machine's runs cut off by its restart, failed (with no org entered: every org's). A run waiting on the
    person is not cut off: it carries on when it is answered; nor is one on a rrotor (dispatched there)."""
    async with engine.begin() as conn:
        mine = (BotRun.machine == here, BotRun.status.in_(("queued", "running")), BotRun.rrotor_id.is_(None))
        cut = update(BotRun).where(*mine).values(status="failed", error=INTERRUPTED, finished_at=now(), session_id="")
        ended = list((await conn.execute(cut.returning(BotRun.id))).scalars())
        await conn.execute(delete(BotSession).where(BotSession.run_id.in_(ended)))  # its session goes with it
        return len(ended)
