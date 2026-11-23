"""A bot as it is shown (BotView): its own fields, the connections it may use (their app joined from the org's
connections), its schedule in plain words, its plugins and where it may run, and its latest run."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import BotRun, Connection
from glyphh_server.ops.bots import installed, package, schedule
from glyphh_server.ops.bots.views import BotView, LastRun, Scope

FIELDS: tuple[str, ...] = (
    *("id", "slug", "name", "summary", "look", "mascot", "instructions", "model", "permission_mode", "voice"),
    *("spec", "skills", "connector_tools", "folders", "effort", "role", "task", "examples"),
)


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
    plugins, places = await installed.shown(conn, bot)
    return BotView(
        **{k: getattr(bot, k) for k in FIELDS},
        gate_models=package.gate_models(bot.slug, bot.spec),
        connections=await _scopes(conn, bot),
        **schedule.shown(bot),
        plugins=plugins,
        can_run_on=places,
        created_at=bot.created_at,
        updated_at=bot.updated_at,
        last_run=await _last(conn, bot.id),
    )
