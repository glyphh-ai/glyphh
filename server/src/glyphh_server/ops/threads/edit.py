"""Changing a thread's record: its goal, pinned to the top of Recents, archived out of it. Deleting one for good,
once it is archived (as rrotor's Settings does it), takes its record, ends every watch of it, and tells its machine
to delete its messages when it is connected."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict
from glyphh_server.link import wire
from glyphh_server.link.hub import Hub
from glyphh_server.models import Thread
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.threads.shape import ThreadRow, mine, my_thread


class ThreadChange(BaseModel):
    goal: str | None = Field(default=None, min_length=1, max_length=500)
    pinned: bool | None = None
    archived: bool | None = None


def _values(change: ThreadChange) -> dict[str, object]:
    values: dict[str, object] = {}
    if change.goal is not None:
        values["goal"] = change.goal.strip()
    if change.pinned is not None:
        values["pinned_at"] = func.now() if change.pinned else None
    if change.archived is not None:
        values["archived_at"] = func.now() if change.archived else None
    return values


async def change_thread(conn: AsyncConnection, who: Principal, thread_id: uuid.UUID, change: ThreadChange) -> ThreadRow:
    await my_thread(conn, who, thread_id)
    values = _values(change)
    if values:
        await conn.execute(update(Thread).where(Thread.id == thread_id, *mine(who)).values(**values))
    return await my_thread(conn, who, thread_id)


async def delete_thread(conn: AsyncConnection, who: Principal, hub: Hub, thread_id: uuid.UUID) -> None:
    thread = await my_thread(conn, who, thread_id)
    if thread.archived_at is None:
        raise Conflict("Archive the thread first; archived threads are deleted for good.", reason="not_archived")
    await conn.execute(delete(Thread).where(Thread.id == thread_id, *mine(who)))
    hub.end(thread_id)
    await hub.tell(thread.machine_id, wire.forget(thread_id))
