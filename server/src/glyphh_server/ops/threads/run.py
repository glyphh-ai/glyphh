"""Working a thread through its machine: starting one (its record first, then the machine is told), saying more,
stopping it. The machine must be connected; when it is not, the member is told so, with when it was last seen."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.link import wire
from glyphh_server.link.hub import Hub
from glyphh_server.models import SuperPower, Thread, ThreadCrew
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.machines.installed import machine_named
from glyphh_server.ops.threads.shape import ThreadRow, my_thread

GOAL_MAX: int = 200


class ThreadStart(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    engine: Literal["claude_code", "codex"] = "claude_code"
    super_power: uuid.UUID | None = None
    crew: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    mode: Literal["driven", "autonomous"] = "driven"


class Say(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


async def _reachable(conn: AsyncConnection, who: Principal, hub: Hub, machine: uuid.UUID) -> None:
    named = await machine_named(conn, who, machine)
    if not hub.online(machine):
        raise Conflict(f"{named.name} is offline.", reason="offline", last_seen_at=str(named.last_seen_at))


async def _mine(conn: AsyncConnection, who: Principal, super_powers: list[uuid.UUID]) -> None:
    found = await conn.execute(
        select(SuperPower.id).where(SuperPower.id.in_(super_powers), SuperPower.user_id == who.user_id)
    )
    if len(set(found.scalars())) != len(set(super_powers)):
        raise NotFound("No such super power of yours.")


def goal_of(prompt: str) -> str:
    """A thread's goal: the first line of what was asked, cut short."""
    first = prompt.strip().splitlines()[0].strip()
    return first if len(first) <= GOAL_MAX else f"{first[: GOAL_MAX - 1]}…"


async def start_thread(
    engine: AsyncEngine, who: Principal, hub: Hub, machine: uuid.UUID, start: ThreadStart
) -> ThreadRow:
    async with engine.begin() as conn:
        await _reachable(conn, who, hub, machine)
        await _mine(conn, who, [sp for sp in [start.super_power, *start.crew] if sp])
        values = {
            "org_id": who.org_id,
            "user_id": who.user_id,
            "machine_id": machine,
            "goal": goal_of(start.prompt),
            "super_power_id": start.super_power,
            "status": "working",
        }
        thread = (await conn.execute(insert(Thread).values(**values).returning(Thread.id))).scalar_one()
        for sp in dict.fromkeys(start.crew):
            await conn.execute(insert(ThreadCrew).values(thread_id=thread, super_power_id=sp))
    await hub.tell(machine, wire.start(thread, start.super_power, start.engine, start.prompt, start.model, start.mode))
    async with engine.connect() as conn:
        return await my_thread(conn, who, thread)


async def _told(conn: AsyncConnection, who: Principal, hub: Hub, thread_id: uuid.UUID, msg: dict[str, object]) -> None:
    thread = await my_thread(conn, who, thread_id)
    await _reachable(conn, who, hub, thread.machine_id)
    await hub.tell(thread.machine_id, msg)


async def say(conn: AsyncConnection, who: Principal, hub: Hub, thread_id: uuid.UUID, text: str) -> None:
    await _told(conn, who, hub, thread_id, wire.say(str(thread_id), text))


async def stop(conn: AsyncConnection, who: Principal, hub: Hub, thread_id: uuid.UUID) -> None:
    await _told(conn, who, hub, thread_id, wire.stop(str(thread_id)))
