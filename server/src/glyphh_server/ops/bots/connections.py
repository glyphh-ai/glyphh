"""The org's connections (docs/specs/bots.md): Pipedream holds each account's sign-in, the server a row naming it. A
link sends someone to Pipedream's page to sign in; a sync then reads the org's accounts back, adding the new ones and
removing the gone. Each call to Pipedream is made with no transaction open, the rows read and written on short ones of
their own."""

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Connection
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots.pipedream import Pipedream
from glyphh_server.ops.bots.views import Apps, AppView, ConnectionView, Link, ToolView

MISSING: str = "The org has no such connection."
PAGE: int = 30


def shown(row: Any) -> ConnectionView:
    return ConnectionView.model_validate(row, from_attributes=True)


async def listing(conn: AsyncConnection) -> list[ConnectionView]:
    rows = await conn.execute(select(Connection).order_by(Connection.app_name, Connection.created_at))
    return [shown(r) for r in rows]


async def row(conn: AsyncConnection, connection_id: uuid.UUID) -> Any:
    found = (await conn.execute(select(Connection).where(Connection.id == connection_id))).first()
    if found is None:
        raise NotFound(MISSING, connection_id=str(connection_id))
    return found


async def apps(pd: Pipedream, q: str | None, cursor: str | None) -> Apps:
    page = await pd.apps(q, cursor)
    data = page.get("data", [])
    listed = [
        AppView(
            slug=a.get("name_slug", ""),
            name=a.get("name", ""),
            description=a.get("description") or "",
            icon=a.get("img_src") or "",
        )
        for a in data
    ]
    after = (page.get("page_info") or {}).get("end_cursor")
    return Apps(apps=listed, next_cursor=after if after and len(data) >= PAGE else None)


async def link(pd: Pipedream, who: Principal, app: str) -> Link:
    return Link(**await pd.link(who.org_id, app))


def _account(org_id: uuid.UUID, account: dict[str, Any]) -> dict[str, Any]:
    app = account.get("app") or {}
    return {
        "org_id": org_id,
        "app": app.get("name_slug", ""),
        "app_name": app.get("name", ""),
        "app_icon": app.get("img_src") or "",
        "account_id": account["id"],
        "label": account.get("name") or "",
    }


async def sync(pd: Pipedream, engine: AsyncEngine, who: Principal) -> list[ConnectionView]:
    """The org's accounts at Pipedream, as its connections: new ones added, gone ones removed."""
    accounts = [a for a in await pd.accounts(who.org_id) if a.get("id") and not a.get("dead")]
    held = [a["id"] for a in accounts]
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        await conn.execute(delete(Connection).where(Connection.account_id.not_in(held)))
        for account in accounts:
            values = _account(who.org_id, account)
            kept = {k: values[k] for k in ("app_name", "app_icon", "label")}
            made = upsert(Connection).values(**values)
            keys = [Connection.org_id, Connection.account_id]
            await conn.execute(made.on_conflict_do_update(index_elements=keys, set_=kept))
        return await listing(conn)


async def _found(engine: AsyncEngine, who: Principal, connection_id: uuid.UUID) -> Any:
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        return await row(conn, connection_id)


async def remove(pd: Pipedream, engine: AsyncEngine, who: Principal, connection_id: uuid.UUID) -> None:
    """The connection deleted, its account at Pipedream too (one Pipedream no longer has is gone already)."""
    found = await _found(engine, who, connection_id)
    try:
        await pd.forget(found.account_id)
    except Invalid as err:
        if err.detail.get("status") != 404:
            raise
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        await conn.execute(delete(Connection).where(Connection.id == connection_id))


async def tools(pd: Pipedream, engine: AsyncEngine, who: Principal, connection_id: uuid.UUID) -> list[ToolView]:
    """What a bot may be let do with the connection: its app's Pipedream actions."""
    found = await _found(engine, who, connection_id)
    return [
        ToolView(key=a["key"], name=a.get("name") or a["key"], description=a.get("description") or "")
        for a in await pd.actions(found.app)
        if a.get("key")
    ]
