"""An org's bots: made, read, changed and deleted on the request's transaction (the org entered). A bot is an agent
(docs/specs/bot-agent-loop.md): its instructions, its standing task and example prompts, what it decides and may
reach (`spec`: its decisions, each an Ada model; hosts; limits), its own notes, and per connection the tools it may
use. What is given is checked before it is kept, every problem said at once. A bot's slug comes from its name at
its making and stays (its Ada models are named by it); a second bot of the same slug is refused. Made, a bot gets an
Ada API key of its own, as the person who made it; deleted, the key is revoked. The org's orchestrator is listed
first and is never deleted (ops/bots/orchestrator.py)."""

import re
from types import SimpleNamespace
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import keys as ada_keys
from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Bot, Connection, RuntimeKey
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.sealed import seal, unseal
from glyphh_server.ops.bots import (
    access,
    cloud,
    exposed,
    orchestrator,
    package,
    places,
    prices,
    schedule,
    seeds,
    shape,
    svg,
    voices,
)
from glyphh_server.ops.bots.botviews import FIELDS, view
from glyphh_server.ops.bots.views import LOOK_PARTS, BotIn, BotPatch, BotView, ScopeIn, ScopesIn
from glyphh_server.ops.runtime_keys import key_hash

MISSING: str = "There is no such bot."
KEY_NAME: str = "bot "  # its own Ada key's name, then its slug: never a person's key (api/key_auth.py)
SPEC: frozenset[str] = frozenset({"gates", "hosts", "builtins", "limits", "seed", "reads_glyphh"})
NO_LOOP: str = (
    "A bot is no longer a loop of steps: say what it does in its instructions (a fixed flow is a program), and the "
    "decisions it can ask Ada about in gates."
)
NEEDS_RROTOR: str = "{name} needs a rrotor: it cannot run on Glyphh cloud. Choose one of your rrotors for it."


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = re.sub(r"^[^a-z]+", "", slug)[: package.SLUG_MAX].strip("-")
    if not slug:
        raise Invalid("A bot's name needs a letter.", reason="name")
    return slug


def _look(given: dict[str, str]) -> dict[str, str]:
    return {k: str(v)[:40] for k, v in given.items() if k in LOOK_PARTS}


def checked(bot: Any) -> None:
    """The bot as it would be kept: its spec of the keys a bot has, its hosts public, its decisions ones the SDK
    holds, its connector tools fitting it."""
    if "loop" in bot.spec:
        raise Invalid(NO_LOOP, reason="spec", problems=[NO_LOOP])
    unknown = sorted(set(bot.spec) - SPEC)
    if unknown:
        said = f"A bot's spec has gates (decisions), hosts, builtins, limits and seed: {', '.join(unknown)} is not one."
        raise Invalid(said, reason="spec", problems=[said])
    cloud.check_hosts(bot.spec)
    seeds.named(bot.spec)
    package.check(bot)
    exposed.check(bot.spec, getattr(bot, "connector_tools", []))  # a maker's draft declares none


async def row(conn: AsyncConnection, slug: str) -> Any:
    found = (await conn.execute(select(Bot).where(Bot.slug == slug))).first()
    if found is None:
        raise NotFound(MISSING, slug=slug)
    return found


async def listing(conn: AsyncConnection, q: str | None = None) -> list[BotView]:
    """The org's bots, its orchestrator first, then by name; with `q`, those whose name, slug or summary has every
    one of its words."""
    found = select(Bot).order_by(Bot.role.desc(), Bot.name)
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


async def made(conn: AsyncConnection, who: Principal, secret: str, body: BotIn) -> Any:
    """The bot's row, made and checked (its view is `create`)."""
    slug = slugify(body.name)
    values: dict[str, Any] = {
        "slug": slug,
        "name": body.name,
        "summary": body.summary,
        "look": _look(body.look),
        "mascot": svg.clean(body.mascot),
        "instructions": body.instructions,
        "model": prices.model(body.model or prices.DEFAULT).id,
        "permission_mode": body.permission_mode,
        "voice": voices.voice(body.voice),
        "spec": body.spec,
        "skills": body.skills,
        "scopes": await _scoped(conn, body.connections),
        "schedule": body.schedule.model_dump(),
        "next_run_at": schedule.next_after(body.schedule, schedule.now()),
        "runs_on": await places.checked(conn, body.runs_on),
        "folders": access.folders(body.folders),
        "effort": body.effort,
        "connector_tools": [t.model_dump(mode="json") for t in body.connector_tools],
        "task": body.task.strip(),
        "examples": shape.examples(body.examples),
    }
    checked(SimpleNamespace(**values, state=None))
    key = await ada_keys.create(conn, who, f"{KEY_NAME}{slug}", None, 0.0)
    values |= {"org_id": who.org_id, "created_by": who.user_id, "ada_key": seal(secret, key.key)}
    return await _saved(conn, Bot.__table__.insert().values(**values), slug)


async def create(conn: AsyncConnection, who: Principal, secret: str, body: BotIn) -> BotView:
    return await view(conn, await made(conn, who, secret, body))


def _changes(body: BotPatch) -> dict[str, Any]:
    given = body.model_dump(exclude_unset=True, exclude={"runs_on"})
    if "look" in given:
        given["look"] = _look(given["look"] or {})
    if "mascot" in given:
        given["mascot"] = svg.clean(given["mascot"] or "")
    if "voice" in given:
        given["voice"] = voices.voice(given["voice"] or "")
    if "model" in given:
        given["model"] = prices.model(given["model"] or prices.DEFAULT).id
    changes = {k: v for k, v in given.items() if v is not None}
    if body.folders is not None:  # the whole list, checked as at its making
        changes["folders"] = access.folders(body.folders)
    if body.examples is not None:
        changes["examples"] = shape.examples(body.examples)
    if body.schedule is not None:  # its next run worked out again, from now
        changes["next_run_at"] = schedule.next_after(body.schedule, schedule.now())
    return changes


async def _changed(conn: AsyncConnection, bot: Any, changes: dict[str, Any]) -> BotView:
    now = {k: getattr(bot, k) for k in (*FIELDS, "scopes", "state")} | changes
    checked(SimpleNamespace(**now))
    statement = Bot.__table__.update().where(Bot.id == bot.id).values(**changes, updated_at=func.now())
    shown = await view(conn, await _saved(conn, statement, bot.slug))
    if shown.runs_on is None and "cloud" not in shown.can_run_on and "runs_on" in changes:
        raise Invalid(NEEDS_RROTOR.format(name=shown.name), reason="runs_on")
    return shown


async def patch(conn: AsyncConnection, slug: str, body: BotPatch) -> BotView:
    changes = _changes(body)
    if "runs_on" in body.model_fields_set:  # null is Glyphh cloud again
        changes["runs_on"] = await places.checked(conn, body.runs_on)
    return await _changed(conn, await row(conn, slug), changes)


async def remove(conn: AsyncConnection, slug: str, secret: str) -> None:
    bot = await row(conn, slug)
    orchestrator.refuse_delete(bot)
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
    """The tools the bot may use, per connection: the whole list, replacing what it had."""
    bot = await row(conn, slug)
    return await _changed(conn, bot, {"scopes": await _scoped(conn, body.connections)})
