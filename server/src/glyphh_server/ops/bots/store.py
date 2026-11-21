"""An org's bots: made, read, changed and deleted on the request's transaction (the org entered), each shown with the
connections it may use (their app joined from the org's connections) and its latest run. A bot's slug comes from its
name and is the org's own; a second bot of the same slug is refused."""

import re
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Bot, BotRun, Connection
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import prices
from glyphh_server.ops.bots.views import LOOK_PARTS, BotIn, BotPatch, BotView, LastRun, Limits, Scope, ScopesIn

MISSING: str = "There is no such bot."
MICROS: int = 1_000_000


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].strip("-")
    if not slug:
        raise Invalid("A bot's name needs a letter or a digit.", reason="name")
    return slug


def _look(given: dict[str, str]) -> dict[str, str]:
    return {k: str(v)[:40] for k, v in given.items() if k in LOOK_PARTS}


def _limits(limits: Limits) -> dict[str, int]:
    return {"max_turns": limits.max_turns, "usd_per_run_micros": round(limits.usd_per_run * MICROS)}


async def _scopes(conn: AsyncConnection, bot: Any) -> list[Scope]:
    ids = [uuid.UUID(s["connection_id"]) for s in bot.scopes]
    rows = await conn.execute(select(Connection).where(Connection.id.in_(ids))) if ids else []
    apps = {r.id: r for r in rows}
    return [
        Scope(connection_id=c.id, app=c.app, app_name=c.app_name, tools=s["tools"])
        for s in bot.scopes
        if (c := apps.get(uuid.UUID(s["connection_id"]))) is not None
    ]


async def _last(conn: AsyncConnection, bot_id: uuid.UUID) -> LastRun | None:
    newest = select(BotRun.id, BotRun.status, BotRun.created_at).where(BotRun.bot_id == bot_id)
    row = (await conn.execute(newest.order_by(BotRun.created_at.desc()).limit(1))).first()
    return None if row is None else LastRun(id=row.id, status=row.status, created_at=row.created_at)


async def view(conn: AsyncConnection, bot: Any) -> BotView:
    limits = Limits(max_turns=bot.max_turns, usd_per_run=bot.usd_per_run_micros / MICROS)
    return BotView(
        **{k: getattr(bot, k) for k in ("id", "slug", "name", "summary", "look", "instructions", "model", "models")},
        connections=await _scopes(conn, bot),
        limits=limits,
        created_at=bot.created_at,
        updated_at=bot.updated_at,
        last_run=await _last(conn, bot.id),
    )


async def row(conn: AsyncConnection, slug: str) -> Any:
    found = (await conn.execute(select(Bot).where(Bot.slug == slug))).first()
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return found


async def listing(conn: AsyncConnection) -> list[BotView]:
    rows = await conn.execute(select(Bot).order_by(Bot.name))
    return [await view(conn, b) for b in rows]


async def one(conn: AsyncConnection, slug: str) -> BotView:
    return await view(conn, await row(conn, slug))


async def _saved(conn: AsyncConnection, statement: Any, slug: str) -> Any:
    try:
        async with conn.begin_nested():
            return (await conn.execute(statement.returning(Bot))).one()
    except IntegrityError as err:
        raise Conflict(f"The org already has a bot {slug!r}: name it another way.", slug=slug) from err


async def create(conn: AsyncConnection, who: Principal, body: BotIn) -> BotView:
    slug = slugify(body.name)
    values = {
        "org_id": who.org_id,
        "created_by": who.user_id,
        "slug": slug,
        "name": body.name,
        "summary": body.summary,
        "look": _look(body.look),
        "instructions": body.instructions,
        "model": prices.model(body.model or prices.DEFAULT).id,
        "models": body.models,
        **_limits(body.limits or Limits()),
    }
    return await view(conn, await _saved(conn, Bot.__table__.insert().values(**values), slug))


def _changes(body: BotPatch) -> dict[str, Any]:
    given = body.model_dump(exclude_unset=True, exclude={"limits"})
    if "name" in given:
        given["slug"] = slugify(given["name"])
    if "look" in given:
        given["look"] = _look(given["look"] or {})
    if "model" in given:
        given["model"] = prices.model(given["model"] or prices.DEFAULT).id
    given = {k: v for k, v in given.items() if v is not None}
    return given | (_limits(body.limits) if body.limits is not None else {})


async def patch(conn: AsyncConnection, slug: str, body: BotPatch) -> BotView:
    bot = await row(conn, slug)
    changes = _changes(body) | {"updated_at": func.now()}
    statement = Bot.__table__.update().where(Bot.id == bot.id).values(**changes)
    return await view(conn, await _saved(conn, statement, changes.get("slug", slug)))


async def remove(conn: AsyncConnection, slug: str) -> None:
    bot = await row(conn, slug)
    await conn.execute(delete(Bot).where(Bot.id == bot.id))


async def set_scopes(conn: AsyncConnection, slug: str, body: ScopesIn) -> BotView:
    """The tools the bot may use, per connection: the whole list, replacing what it had."""
    bot = await row(conn, slug)
    ids = {s.connection_id for s in body.connections}
    found = set((await conn.scalars(select(Connection.id).where(Connection.id.in_(ids)))).all()) if ids else set()
    if missing := ids - found:
        raise NotFound("The org has no such connection.", connection_ids=sorted(str(i) for i in missing))
    scopes = [{"connection_id": str(s.connection_id), "tools": sorted(set(s.tools))} for s in body.connections]
    statement = Bot.__table__.update().where(Bot.id == bot.id).values(scopes=scopes, updated_at=func.now())
    return await view(conn, await _saved(conn, statement, slug))
