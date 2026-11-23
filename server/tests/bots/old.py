"""Bots as they were while a bot was a loop of steps, for the conversion's tests: the eight templates Glyphh shipped
then (tests/bots/old_library/<slug>.json: each file as it was on main before the change, its `description` left
out), and a bot put in the database the way installing one made it then (its row written straight, since the API
no longer makes a loop bot)."""

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Bot, BotPlugin, BotRun
from glyphh_server.ops.bots import converted
from glyphh_server.ops.bots.schedule import Schedule
from tests.bots.conftest import Served, made_bot
from tests.bots.market import linked
from tests.db.helpers import Person

LIBRARY: Path = Path(__file__).with_name("old_library")
SLUGS: list[str] = sorted(p.stem for p in LIBRARY.glob("*.json"))


def template(slug: str) -> dict[str, Any]:
    return dict(json.loads((LIBRARY / f"{slug}.json").read_text("utf-8")))


async def looped(s: Served, engine: AsyncEngine, who: Person, was: dict[str, Any], **over: Any) -> dict[str, Any]:
    """The bot installing `was` made on main: scoped to the org's connection of each app (the app's own tools),
    with the template's loop, instructions, notes, schedule and connector tools; `over` changes its row."""
    mine = await linked(s, who, *was.get("apps", []))
    scopes = [
        {"connection_id": mine[a]["id"], "tools": [k for k in was["tools"] if k.split("-", 1)[0] == a] or was["tools"]}
        for a in was.get("apps", [])
    ]
    body = {"name": was["name"], "summary": was.get("summary", ""), "instructions": was["instructions"]}
    bot = await made_bot(s, who, **body, spec={}, skills={}, connections=scopes, task="", examples=[])
    values = {"spec": was["spec"], "skills": was.get("skills", {}), "look": was.get("look", {}), "model": was["model"]}
    values |= {"schedule": Schedule(**was.get("schedule", {})).model_dump()}
    values |= {"connector_tools": was.get("connector_tools", [])}
    async with engine.begin() as conn:
        await conn.execute(update(Bot).where(Bot.id == uuid.UUID(bot["id"])).values(**values | over))
    return bot


async def convert(engine: AsyncEngine) -> dict[str, int]:
    """The conversion, as the schema step runs it."""
    async with engine.begin() as conn:
        return await converted.convert(conn)


async def row(engine: AsyncEngine, bot_id: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(select(Bot).where(Bot.id == uuid.UUID(str(bot_id))))).one()


async def plugins(engine: AsyncEngine, bot_id: Any) -> list[Any]:
    async with engine.connect() as conn:
        return list(await conn.execute(select(BotPlugin).where(BotPlugin.bot_id == uuid.UUID(str(bot_id)))))


async def a_run(engine: AsyncEngine, who: Person, bot_id: Any, status: str, **more: Any) -> uuid.UUID:
    """A run of the bot left as the old engine left it."""
    values = {"org_id": who.org_id, "bot_id": uuid.UUID(str(bot_id)), "user_id": who.user_id, "status": status}
    async with engine.begin() as conn:
        made: uuid.UUID = (await conn.execute(insert(BotRun).values(**values | more).returning(BotRun.id))).scalar_one()
    return made
