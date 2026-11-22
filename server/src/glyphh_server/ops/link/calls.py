"""Glyphh's own programs called on one of the org's rrotors over its link (docs/specs/bots.md, 9 and 10): glyphh_bot
for a bot's run, glyphh_swarm for a project's steps. The rrotor must be the org's and hold its link right now (its
state, ops/link/presence.py), else the run is refused saying so; a call must fit in one message of the link (rrotor
takes LINK_MAX bytes), else it is refused before it is sent. Its version is left to the rrotor (null: the one active
there, its built-in). A message the hub cannot deliver (no process holds the link) is said by False."""

import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Invalid
from glyphh_server.ops.bots import places
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.protocol import Call, Cancel, Continue

LINK_MAX: int = 4 * 1024 * 1024  # one message rrotor's link reads (aiohttp's default)
MARGIN: int = 4 * 1024  # the call's own fields, past its inputs


def offline(name: str) -> str:
    return f"{name} is not linked to Glyphh right now: start it, or check its link, then try again."


async def linked(conn: AsyncConnection, rrotor_id: uuid.UUID) -> places.Place:
    """The org's rrotor, linked now; else refused (Invalid when it is not the org's, Conflict when it is offline)."""
    found = await places.one(conn, rrotor_id)
    if not found.linked:
        raise Conflict(offline(found.name), reason="rrotor_offline", runs_on=str(rrotor_id))
    return found


def fits(inputs: dict[str, Any], what: str) -> None:
    """The call's inputs fit in one message of the link, or Invalid says how big they are."""
    big = len(json.dumps(inputs, separators=(",", ":"), default=str).encode()) + MARGIN
    if big > LINK_MAX:
        raise Invalid(
            f"{what} is {big / 1_000_000:.1f} MB, more than a rrotor's link takes in one message "
            f"({LINK_MAX / 1_000_000:.1f} MB): run it on Glyphh cloud.",
            reason="too_big",
            size=big,
        )


async def call(
    hub: Hub,
    rrotor_id: uuid.UUID,
    run_id: uuid.UUID,
    program: str,
    function: str,
    inputs: dict[str, Any],
    folders: list[dict[str, str]] | None = None,
) -> bool:
    """The call sent; `folders` the machine's folders its run is given (none: null, as a rrotor of any version
    reads it)."""
    sent = Call(run_id=run_id, program=program, function=function, inputs=inputs, folders=folders or None)
    return await hub.deliver(rrotor_id, sent)


async def carry_on(hub: Hub, rrotor_id: uuid.UUID, run_id: uuid.UUID, answer: Any) -> bool:
    return await hub.deliver(rrotor_id, Continue(run_id=run_id, answer=answer))


async def cancel(hub: Hub, rrotor_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    return await hub.deliver(rrotor_id, Cancel(run_id=run_id))
