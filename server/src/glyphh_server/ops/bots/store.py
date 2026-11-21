"""An org's bots: made, read, changed and deleted on the request's transaction (the org entered), each shown with the
connections it may use (their app joined from the org's connections) and its latest run. A bot is the SDK's bot
package (ops/bots/package.py): what is given is checked by the SDK before it is kept, every problem said at once,
against the tools its scope lets it use. A bot's slug comes from its name at its making and stays (its Ada models are
named by it); a second bot of the same slug is refused. Made, a bot gets an Ada API key of its own, as the person
who made it, for its gates and memory; deleted, the key is revoked."""

import re
import uuid
from types import SimpleNamespace
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import keys as ada_keys
from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Bot, BotRun, Connection, RuntimeKey
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.sealed import seal, unseal
from glyphh_server.ops.bots import cloud, package, prices
from glyphh_server.ops.bots.views import LOOK_PARTS, BotIn, BotPatch, BotView, LastRun, Scope, ScopeIn, ScopesIn
from glyphh_server.ops.runtime_keys import key_hash

MISSING: str = "There is no such bot."
FIELDS: tuple[str, ...] = ("id", "slug", "name", "summary", "look", "instructions", "model", "spec", "skills")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = re.sub(r"^[^a-z]+", "", slug)[: package.SLUG_MAX].strip("-")
    if not slug:
        raise Invalid("A bot's name needs a letter.", reason="name")
    return slug


def _look(given: dict[str, str]) -> dict[str, str]:
    return {k: str(v)[:40] for k, v in given.items() if k in LOOK_PARTS}


def checked(bot: Any) -> None:
    """The bot as it would be kept, checked by the SDK against the tools its scope names."""
    cloud.check_hosts(bot.spec)
    package.check(bot, cloud.Program(cloud.named(bot.scopes)))


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
    return BotView(
        **{k: getattr(bot, k) for k in FIELDS},
        gate_models=package.gate_models(bot.slug, bot.spec),
        connections=await _scopes(conn, bot),
        created_at=bot.created_at,
        updated_at=bot.updated_at,
        last_run=await _last(conn, bot.id),
    )


async def row(conn: AsyncConnection, slug: str) -> Any:
    found = (await conn.execute(select(Bot).where(Bot.slug == slug))).first()
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return found


async def listing(conn: AsyncConnection, q: str | None = None) -> list[BotView]:
    """The org's bots by name; with `q`, those whose name, slug or summary has every one of its words."""
    found = select(Bot).order_by(Bot.name)
    for word in (q or "").split():
        found = found.where((Bot.name + " " + Bot.slug + " " + Bot.summary).icontains(word, autoescape=True))
    return [await view(conn, b) for b in await conn.execute(found)]


async def one(conn: AsyncConnection, slug: str) -> BotView:
    return await view(conn, await row(conn, slug))


async def _saved(conn: AsyncConnection, statement: Any, slug: str) -> Any:
    try:
        async with conn.begin_nested():
            return (await conn.execute(statement.returning(Bot))).one()
    except IntegrityError as err:
        raise Conflict(f"The org already has a bot {slug!r}: name it another way.", slug=slug) from err


async def create(conn: AsyncConnection, who: Principal, secret: str, body: BotIn) -> BotView:
    slug = slugify(body.name)
    values: dict[str, Any] = {
        "slug": slug,
        "name": body.name,
        "summary": body.summary,
        "look": _look(body.look),
        "instructions": body.instructions,
        "model": prices.model(body.model or prices.DEFAULT).id,
        "spec": body.spec,
        "skills": body.skills,
        "scopes": await _scoped(conn, body.connections),
    }
    checked(SimpleNamespace(**values, state=None))
    made = await ada_keys.create(conn, who, f"bot {slug}", None, 0.0)
    values |= {"org_id": who.org_id, "created_by": who.user_id, "ada_key": seal(secret, made.key)}
    return await view(conn, await _saved(conn, Bot.__table__.insert().values(**values), slug))


def _changes(body: BotPatch) -> dict[str, Any]:
    given = body.model_dump(exclude_unset=True)
    if "look" in given:
        given["look"] = _look(given["look"] or {})
    if "model" in given:
        given["model"] = prices.model(given["model"] or prices.DEFAULT).id
    return {k: v for k, v in given.items() if v is not None}


async def _changed(conn: AsyncConnection, bot: Any, changes: dict[str, Any]) -> BotView:
    now = {k: getattr(bot, k) for k in (*FIELDS, "scopes", "state")} | changes
    checked(SimpleNamespace(**now))
    statement = Bot.__table__.update().where(Bot.id == bot.id).values(**changes, updated_at=func.now())
    return await view(conn, await _saved(conn, statement, bot.slug))


async def patch(conn: AsyncConnection, slug: str, body: BotPatch) -> BotView:
    return await _changed(conn, await row(conn, slug), _changes(body))


async def remove(conn: AsyncConnection, slug: str, secret: str) -> None:
    bot = await row(conn, slug)
    hashed = key_hash(unseal(secret, bot.ada_key))
    await conn.execute(update(RuntimeKey).where(RuntimeKey.key_hash == hashed).values(revoked_at=func.now()))
    await conn.execute(delete(Bot).where(Bot.id == bot.id))


async def _scoped(conn: AsyncConnection, given: list[ScopeIn]) -> list[dict[str, Any]]:
    ids = {s.connection_id for s in given}
    found = set((await conn.scalars(select(Connection.id).where(Connection.id.in_(ids)))).all()) if ids else set()
    if missing := ids - found:
        raise NotFound("The org has no such connection.", connection_ids=sorted(str(i) for i in missing))
    return [{"connection_id": str(s.connection_id), "tools": sorted(set(s.tools))} for s in given]


async def set_scopes(conn: AsyncConnection, slug: str, body: ScopesIn) -> BotView:
    """The tools the bot may use, per connection: the whole list, replacing what it had (its loop checked again)."""
    bot = await row(conn, slug)
    return await _changed(conn, bot, {"scopes": await _scoped(conn, body.connections)})
