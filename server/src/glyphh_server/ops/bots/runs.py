"""A bot's runs in the database: made queued, started, each step appended as it is taken (so a run's page shows it
going), its tokens added after each of Claude's turns, and ended done or failed. A run records the machine running it:
when that machine starts again, its runs still queued or running were cut off, and are failed."""

import os
import socket
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import literal, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import NotFound
from glyphh_server.models import Bot, BotRun
from glyphh_server.ops.bots.views import RunView

MISSING: str = "There is no such run."
INTERRUPTED: str = "interrupted by a restart"
SHOWN: int = 50


def machine() -> str:
    return os.environ.get("FLY_MACHINE_ID") or socket.gethostname()


def now() -> datetime:
    return datetime.now(UTC)


def view(run: Any, slug: str) -> RunView:
    fields = RunView.model_fields.keys() - {"bot_slug"}
    return RunView(bot_slug=slug, **{k: getattr(run, k) for k in fields})


async def get(conn: AsyncConnection, run_id: uuid.UUID) -> RunView:
    found = (
        await conn.execute(select(BotRun, Bot.slug).join(Bot, Bot.id == BotRun.bot_id).where(BotRun.id == run_id))
    ).first()
    if found is None:
        raise NotFound(MISSING, run_id=str(run_id))
    return view(found, found.slug)


async def listing(conn: AsyncConnection, bot: Any) -> list[RunView]:
    newest = select(BotRun).where(BotRun.bot_id == bot.id).order_by(BotRun.created_at.desc()).limit(SHOWN)
    return [view(r, bot.slug) for r in await conn.execute(newest)]


async def create(engine: AsyncEngine, org_id: uuid.UUID, bot: Any, user_id: uuid.UUID, given: str) -> RunView:
    """The run, queued and committed, so its task finds it."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        values = {"org_id": org_id, "bot_id": bot.id, "user_id": user_id, "input": given, "machine": machine()}
        made = (await conn.execute(BotRun.__table__.insert().values(**values).returning(BotRun))).one()
    return view(made, bot.slug)


async def _set(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, **values: Any) -> None:
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        await conn.execute(update(BotRun).where(BotRun.id == run_id).values(**values))


async def start(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
    await _set(engine, org_id, run_id, status="running", started_at=now())


async def step(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, taken: dict[str, Any]) -> None:
    added = literal([{**taken, "at": now().isoformat()}], JSONB)
    await _set(engine, org_id, run_id, steps=BotRun.steps.op("||")(added))


async def used(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, tokens: tuple[int, int, int]) -> None:
    """One of Claude's turns: its input and output tokens and their charge in microdollars, added."""
    i, o, cost = tokens
    more = {
        "input_tokens": BotRun.input_tokens + i,
        "output_tokens": BotRun.output_tokens + o,
        "cost_micros": BotRun.cost_micros + cost,
    }
    await _set(engine, org_id, run_id, **more)


async def finish(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID, output: str, error: str = "") -> None:
    status = "failed" if error else "done"
    await _set(engine, org_id, run_id, status=status, output=output, error=error, finished_at=now())


async def recover(engine: AsyncEngine, here: str) -> int:
    """This machine's runs cut off by its restart, failed (with no org entered: every org's)."""
    async with engine.begin() as conn:
        cut = (
            update(BotRun)
            .where(BotRun.machine == here, BotRun.status.in_(("queued", "running")))
            .values(status="failed", error=INTERRUPTED, finished_at=now())
        )
        return (await conn.execute(cut)).rowcount
