"""`search_tool` (docs/specs/programs.md, 6): the tools a bot or a program could use, found by words: every action of
the apps the org has connected (Pipedream's), and Glyphh's built-ins; with a bot named, whether it has each already.
A found tool is added to a bot as its connection's tool (its scope), a built-in to its built-ins: bots and programs
get tools the same way. Each call to Pipedream is made with no transaction open."""

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Bot, Connection
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import builtins
from glyphh_server.ops.bots.agent.tools import reads
from glyphh_server.ops.bots.pipedream import Pipedream
from glyphh_server.ops.bots.store import row as bot_row
from glyphh_server.ops.programs.views import AddToolIn, FoundTool

MOST: int = 50
NO_CONNECTION: str = "The org has no such connection."
NO_TOOL: str = "{app} has no tool {tool}."
BUILT_IN_APP: str = "Glyphh"


def _fits(words: list[str], *said: str) -> bool:
    text = " ".join(said).lower()
    return all(w in text for w in words)


async def _read(engine: AsyncEngine, who: Principal, bot: str | None) -> tuple[list[Any], Any]:
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        linked = list(await conn.execute(select(Connection).order_by(Connection.app_name, Connection.created_at)))
        return linked, await bot_row(conn, bot) if bot else None


def _built(words: list[str], has: Any) -> list[FoundTool]:
    own = set((has.spec.get("builtins") or []) if has is not None else [])
    return [
        FoundTool(key=k, title=t, app=BUILT_IN_APP, description=d, read_only=r, connection_id=None, added=k in own)
        for k, (t, d, r) in builtins.ABOUT.items()
        if _fits(words, k, t, d)
    ]


async def search(pd: Pipedream, engine: AsyncEngine, who: Principal, q: str, bot: str | None) -> list[FoundTool]:
    """The tools whose name, app or description has every word of `q`, the built-ins first, at most MOST."""
    words = q.lower().split()
    linked, has = await _read(engine, who, bot)
    scoped = {(s["connection_id"], k) for s in (has.scopes if has is not None else []) for k in s["tools"]}
    found = _built(words, has)
    for c in linked if pd.on else []:
        for a in await pd.actions(c.app):
            key, title = a.get("key") or "", str(a.get("name") or a.get("key") or "")
            if key and _fits(words, key, title, c.app_name, str(a.get("description") or "")):
                found.append(
                    FoundTool(key=key, title=title, app=c.app_name, description=str(a.get("description") or "")[:500],
                              read_only=reads(key, a), connection_id=c.id, added=(str(c.id), key) in scoped)
                )  # fmt: skip
            if len(found) >= MOST:
                return found
    return found


def _scopes(scopes: list[dict[str, Any]], connection_id: str, tool: str) -> list[dict[str, Any]]:
    had = {s["connection_id"]: list(s["tools"]) for s in scopes}
    had[connection_id] = sorted({*had.get(connection_id, []), tool})
    return [{"connection_id": c, "tools": t} for c, t in had.items()]


async def add(pd: Pipedream, engine: AsyncEngine, who: Principal, slug: str, body: AddToolIn) -> None:
    """The found tool given to the bot: a built-in among its built-ins, else its connection's tool in its scope."""
    if body.connection_id is None:
        if body.tool not in builtins.ABOUT:
            raise Invalid(NO_TOOL.format(app=BUILT_IN_APP, tool=body.tool), reason="tool")
        async with engine.begin() as conn:
            await tenancy.enter(conn, who.org_id)
            bot = await bot_row(conn, slug)
            spec = {**bot.spec, "builtins": sorted({*(bot.spec.get("builtins") or []), body.tool})}
            await conn.execute(update(Bot).where(Bot.id == bot.id).values(spec=spec))
        return
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        c = (await conn.execute(select(Connection).where(Connection.id == body.connection_id))).one_or_none()
    if c is None:
        raise NotFound(NO_CONNECTION, connection_id=str(body.connection_id))
    if body.tool not in {a.get("key") for a in await pd.actions(c.app)}:
        raise Invalid(NO_TOOL.format(app=c.app_name, tool=body.tool), reason="tool")
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        bot = await bot_row(conn, slug)
        scopes = _scopes(bot.scopes, str(c.id), body.tool)
        await conn.execute(update(Bot).where(Bot.id == bot.id).values(scopes=scopes))
