"""A bot's runs in the database: made queued (a bot has one live run at a time: queued, running, dispatched to its
rrotor, or waiting on the person), started, and ended with what the runner left: done, failed, skipped by a hard
limit, or needs_input with the question it waits on (answered, the same run is queued again and carries on). A run
records the machine running it: when that machine starts again, its runs still queued or running were cut off, and
are failed; a run on a rrotor is the rrotor's, never cut off by a restart here."""

import os
import re
import socket
import uuid
from datetime import UTC, datetime
from typing import Any

from glyphh.bots import RunResult
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Bot, BotRun
from glyphh_server.ops.bots import said, shown
from glyphh_server.ops.bots.runs_words import INTERRUPTED
from glyphh_server.ops.bots.views import Question, RunView

MISSING: str = "There is no such run."
LIVE: str = "The bot has a run going or waiting on an answer: answer it, or cancel it, first."
SHOWN: int = 50
# A run read with its bot: what the bot is, for what the run says of itself (ops/bots/said.py)
BOT = (Bot.slug, Bot.name.label("bot_name"), Bot.summary.label("bot_summary"), Bot.spec.label("bot_spec"))
TOLD: frozenset[str] = frozenset({"bot_slug", "question", "runs_on", "kind", "project_slug", *shown.Shown.model_fields})


def machine() -> str:
    return os.environ.get("FLY_MACHINE_ID") or socket.gethostname()


def now() -> datetime:
    return datetime.now(UTC)


def view(run: Any, slug: str, name: str, about: str, spec: dict[str, Any]) -> RunView:
    """The run as it is shown: its record, and what it says of itself (a plain summary, a hint when the text it was
    given did not fit the bot, the pages and MCP Apps its steps brought back)."""
    asked = Question(**run.question) if run.question else None
    words = {"summary": said.summary(run, spec), "hint": said.hint(run, spec, name, about)}
    back = {"links": shown.links(run), "apps": shown.apps(run)}
    kept = {k: getattr(run, k) for k in RunView.model_fields.keys() - TOLD}
    return RunView(bot_slug=slug, question=asked, runs_on=run.rrotor_id, **words, **back, **kept)


def joined(found: Any) -> RunView:
    """A run read with its bot (BOT)."""
    return view(found, found.slug, found.bot_name, found.bot_summary, found.bot_spec)


def of(run: Any, bot: Any) -> RunView:
    return view(run, bot.slug, bot.name, bot.summary, bot.spec)


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
    await put(engine, org_id, run_id, status="running", started_at=now(), own_key=own_key)


def _question(result: RunResult) -> dict[str, Any]:
    if result.status != "needs_input":
        return {}
    asked = {"question": result.question or result.reason, "options": result.options or []}
    shown = re.sub(r"^glyphh bot continue \S+\s*", "", result.answer_with) if result.answer_with else None
    where = {"step": result.step, "approval": bool(result.approval)}  # an approval's step: approvals.granted
    return asked | {"batch": result.batch, "answer_with": shown} | where


async def ended(
    engine: AsyncEngine, run: Any, result: RunResult, out: str, tokens: dict[str, int], charged: int, **more: Any
) -> None:
    """What the runner left: the run's status, log, data, question and output; its tokens added to what it had (and
    `more`: a run on a rrotor's own)."""
    values: dict[str, Any] = {
        "status": result.status,
        "error": result.reason if result.status != "needs_input" else "",
        "log": result.log,
        "data": result.data,
        "question": _question(result),
        "output": out,
        "loop_run": result.run_id or "",
        "input_tokens": BotRun.input_tokens + tokens["input_tokens"],
        "output_tokens": BotRun.output_tokens + tokens["output_tokens"],
        "cost_micros": BotRun.cost_micros + charged,
    }
    if result.status != "needs_input":
        values["finished_at"] = now()
    await put(engine, run.org_id, run.id, **values, **more)


async def failed(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, error: str) -> None:
    await put(engine, org_id, run_id, status="failed", error=error, question={}, finished_at=now())


async def recover(engine: AsyncEngine, here: str) -> int:
    """This machine's runs cut off by its restart, failed (with no org entered: every org's). A run waiting on the
    person is not cut off: it carries on when it is answered; nor is one on a rrotor (dispatched there)."""
    async with engine.begin() as conn:
        mine = (BotRun.machine == here, BotRun.status.in_(("queued", "running")), BotRun.rrotor_id.is_(None))
        cut = update(BotRun).where(*mine).values(status="failed", error=INTERRUPTED, finished_at=now())
        return (await conn.execute(cut)).rowcount
