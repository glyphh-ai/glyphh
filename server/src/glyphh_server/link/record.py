"""What a machine's reports change on the server: it is online or not and its version; a thread's status, its newest
event's number and time; a question opened. Only a thread of this machine's, and never what was said."""

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.link.wire import SessionEvent
from glyphh_server.models import THREAD_STATUSES, Machine, NeedsYou, Thread

DETAIL_MAX: int = 200


async def machine_by_token(conn: AsyncConnection, token_hash: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID] | None:
    """The machine a token belongs to (its id, org and member), or None: unknown and revoked are one answer."""
    found = await conn.execute(
        select(Machine.id, Machine.org_id, Machine.user_id).where(
            Machine.token_hash == token_hash, Machine.revoked_at.is_(None)
        )
    )
    row = found.first()
    return None if row is None else (row.id, row.org_id, row.user_id)


async def seen(conn: AsyncConnection, machine: uuid.UUID, online: bool, version: str | None = None) -> None:
    values: dict[str, Any] = {"online": online, "last_seen_at": func.now()}
    if version:
        values["version"] = version
    await conn.execute(update(Machine).where(Machine.id == machine).values(**values))


async def event(conn: AsyncConnection, machine: uuid.UUID, report: SessionEvent) -> bool:
    """Applies one event to its thread's record; False when the thread is not this machine's."""
    values: dict[str, Any] = {"last_seq": func.greatest(Thread.last_seq, report.seq), "last_event_at": func.now()}
    status = report.event.get("status")
    if report.event.get("kind") == "status" and status in THREAD_STATUSES:
        values["status"] = status
    done = await conn.execute(
        update(Thread)
        .where(Thread.id == report.thread, Thread.machine_id == machine)
        .values(**values)
        .returning(Thread.org_id, Thread.user_id)
    )
    owner = done.first()
    if owner is None:
        return False
    if report.event.get("kind") == "needs_you":
        await _asked(conn, owner.org_id, owner.user_id, report)
    return True


async def _asked(conn: AsyncConnection, org: uuid.UUID, user: uuid.UUID, report: SessionEvent) -> None:
    e = report.event
    values = {
        "org_id": org,
        "user_id": user,
        "thread_id": report.thread,
        "super_power_id": report.super_power,
        "session": report.session,
        "ask_id": str(e.get("id", ""))[:200],
        "kind": "permission",
        "tool": str(e.get("tool", "tool"))[:200],
        "detail": str(e.get("detail", ""))[:DETAIL_MAX],
    }
    await conn.execute(insert(NeedsYou).values(**values).on_conflict_do_nothing(index_elements=["thread_id", "ask_id"]))
