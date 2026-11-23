"""The plugins installed for a bot (bot_plugins; docs/specs/bot-agent-loop.md, 7.2): a template's package kept by
path at the version installed, so a bot keeps what it installed until its owner updates it. A bot whose plugin
carries code, or needs folders, can run only on a rrotor. Updating a plugin replaces its files with the library's
and adds the decisions and required tools the new version names; it never touches what the person edited, or what a
decision has learned."""

import copy
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Bot, BotPlugin, Connection
from glyphh_server.ops.bots import packages
from glyphh_server.ops.bots.agent.plugins import NOTES, SIDECAR
from glyphh_server.ops.bots.shape import PLACES, Place, PluginView

TEMPLATE: str = "template:"
MISSING: str = "The bot has no such plugin from a template."


def _latest(row: Any) -> str:
    found = packages.library().get(row.source.removeprefix(TEMPLATE)) if row.source.startswith(TEMPLATE) else None
    return found.version if found is not None else str(row.version)


def _needs_rrotor(files: dict[str, str]) -> bool:
    side = json.loads(files.get(SIDECAR) or "{}")
    return bool(side.get("code")) or bool(side.get("folders"))


async def shown(conn: AsyncConnection, bot: Any) -> tuple[list[PluginView], list[Place]]:
    """The bot's plugins as its view says them (its own notes last), and where it may run."""
    rows = list(await conn.execute(select(BotPlugin).where(BotPlugin.bot_id == bot.id).order_by(BotPlugin.name)))
    views = [PluginView(name=r.name, version=r.version, latest=_latest(r), source=r.source) for r in rows]
    if bot.skills:
        views.append(PluginView(name=NOTES, version="1.0.0", latest="1.0.0", source="personal"))
    rrotor_only = any(_needs_rrotor(r.files) for r in rows)
    return views, ["rrotor"] if rrotor_only else list(PLACES)


async def keep(conn: AsyncConnection, bot: Any, package: packages.Package) -> None:
    """The package's files kept as the bot's plugin, at the package's version (replacing an earlier one's)."""
    values = {"org_id": bot.org_id, "bot_id": bot.id, "name": package.slug, "version": package.version}
    values |= {"source": TEMPLATE + package.slug, "files": package.files}
    made = insert(BotPlugin).values(**values)
    changed = {"version": made.excluded.version, "files": made.excluded.files}
    await conn.execute(made.on_conflict_do_update(index_elements=["bot_id", "name"], set_=changed))


async def _scoped(conn: AsyncConnection, bot: Any, side: packages.Sidecar) -> list[dict[str, Any]]:
    """The bot's scopes with the tools the package requires added: to the bot's own connection of each app, else to
    the org's first connection of it. No tool the bot has is taken away. Invalid names the apps not connected."""
    linked = list(await conn.execute(select(Connection).order_by(Connection.created_at)))
    app_of = {str(c.id): c.app for c in linked}
    scopes = [{"connection_id": s["connection_id"], "tools": list(s["tools"])} for s in bot.scopes]
    missing = []
    for need in side.requires:
        scope = next((s for s in scopes if app_of.get(s["connection_id"]) == need.app), None)
        first = next((str(c.id) for c in linked if c.app == need.app), None)
        if scope is not None:
            scope["tools"] = sorted({*scope["tools"], *need.tools})
        elif first is not None:
            scopes.append({"connection_id": first, "tools": sorted(set(need.tools))})
        else:
            missing.append(need.app)
    if missing:
        said = f"Connect {', '.join(missing)} first: the new version uses it."
        raise Invalid(said, reason="connections", apps=missing)
    return scopes


async def update(conn: AsyncConnection, bot: Any, name: str) -> None:
    """The bot's plugin `name` brought to the library's version: its files replaced, the decisions, hosts and
    required tools the new version adds added to the bot (one the bot has already is left as it is)."""
    row = (await conn.execute(select(BotPlugin).where(BotPlugin.bot_id == bot.id, BotPlugin.name == name))).first()
    package = packages.library().get(row.source.removeprefix(TEMPLATE)) if row is not None else None
    if package is None:
        raise NotFound(MISSING, slug=bot.slug, plugin=name)
    side = package.sidecar
    scopes = await _scoped(conn, bot, side)
    await keep(conn, bot, package)
    more = {
        "gates": {**copy.deepcopy(side.decisions), **(bot.spec.get("gates") or {})},
        "hosts": sorted({*side.hosts, *(bot.spec.get("hosts") or [])}),
        "builtins": sorted({*side.builtins, *(bot.spec.get("builtins") or [])}),
    }
    spec = dict(bot.spec) | {k: v for k, v in more.items() if v}
    await conn.execute(Bot.__table__.update().where(Bot.id == bot.id).values(spec=spec, scopes=scopes))
