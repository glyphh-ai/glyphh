"""Where a bot runs (docs/specs/bots.md, 9): Glyphh cloud (bots.runs_on empty, the default), or one of the org's own
rrotors: a local one (on someone's computer, named by its install) or a self-hosted one (named by the person). Only
the org's are offered or taken (the rrotors its people own, as row-level security shows them; a local one whose
install was signed out is gone). `linked` is whether it holds its link to Glyphh right now (its state, set at its
hello and its link's close, ops/link/presence.py): a run of a bot on a rrotor is sent there over that link
(ops/bots/remote.py), refused while the rrotor is offline. A swarm runs on one of these rrotors too."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import Install, Rrotor
from glyphh_server.ops.link.presence import ONLINE

CLOUD: str = "Glyphh cloud"
LOCAL: str = "Local rrotor"
NOT_ORGS: str = "That is not one of the org's rrotors: GET /v1/bots/places lists where its bots can run."


class Place(BaseModel):
    id: uuid.UUID | None = Field(description="The rrotor's id; none for Glyphh cloud")
    name: str
    mode: Literal["cloud", "local", "self"] = Field(description="cloud (Glyphh's), local or self (self-hosted)")
    linked: bool = Field(description="It holds its link to Glyphh right now (Glyphh cloud always)")


class Places(BaseModel):
    places: list[Place]


async def listing(conn: AsyncConnection) -> Places:
    """Glyphh cloud first, then the org's rrotors by name."""
    found = (
        select(Rrotor.id, Rrotor.mode, Rrotor.name, Rrotor.state, Install.name.label("device"))
        .outerjoin(Install, Install.id == Rrotor.install_id)
        .where(Install.revoked_at.is_(None))
    )
    rrotors = [
        Place(id=r.id, name=r.name or r.device or LOCAL, mode=r.mode, linked=r.state == ONLINE)
        for r in await conn.execute(found)
    ]
    cloud = Place(id=None, name=CLOUD, mode="cloud", linked=True)
    return Places(places=[cloud, *sorted(rrotors, key=lambda p: (p.name.lower(), str(p.id)))])


async def checked(conn: AsyncConnection, runs_on: uuid.UUID | None) -> uuid.UUID | None:
    """Where the bot is to run, refused unless it is Glyphh cloud or one of the org's rrotors."""
    if runs_on is not None and runs_on not in {p.id for p in (await listing(conn)).places}:
        raise Invalid(NOT_ORGS, reason="runs_on", runs_on=str(runs_on))
    return runs_on
