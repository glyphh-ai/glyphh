"""A person's workspace names, for the plan's limit: the mod registers one when it makes it and removes it when it
deletes it. Nothing of what is in a workspace comes here."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Workspace
from glyphh_server.ops import limits
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.guards import taken
from glyphh_server.ops.plans import org_version


class WorkspaceView(BaseModel):
    name: str
    created_at: datetime


_COLUMNS = (Workspace.name, Workspace.created_at)


async def list_workspaces(conn: AsyncConnection, who: Principal) -> list[WorkspaceView]:
    rows = await conn.execute(select(*_COLUMNS).where(Workspace.user_id == who.user_id).order_by(Workspace.created_at))
    return [WorkspaceView(**r._mapping) for r in rows]


async def create_workspace(conn: AsyncConnection, who: Principal, name: str) -> WorkspaceView:
    await limits.lock_user(conn, who.user_id)
    used = await limits.workspaces(conn, who.user_id)
    await limits.check(conn, "workspaces", used, await org_version(conn, who.org_id))
    with taken("You already have a workspace with that name.", name=name):
        row = (await conn.execute(insert(Workspace).values(user_id=who.user_id, name=name).returning(*_COLUMNS))).one()
    return WorkspaceView(**row._mapping)


async def rename_workspace(conn: AsyncConnection, who: Principal, name: str, new_name: str) -> WorkspaceView:
    with taken("You already have a workspace with that name.", name=new_name):
        row = (
            await conn.execute(
                update(Workspace)
                .where(Workspace.user_id == who.user_id, Workspace.name == name)
                .values(name=new_name)
                .returning(*_COLUMNS)
            )
        ).first()
    if row is None:
        raise NotFound("You have no workspace with that name.", name=name)
    return WorkspaceView(**row._mapping)


async def delete_workspace(conn: AsyncConnection, who: Principal, name: str) -> None:
    gone = await conn.execute(delete(Workspace).where(Workspace.user_id == who.user_id, Workspace.name == name))
    if gone.rowcount == 0:
        raise NotFound("You have no workspace with that name.", name=name)
