"""Where a bot runs (docs/specs/bots.md, 9): Glyphh cloud (bots.runs_on empty, the default), or one of the org's own
rrotors: a local one (on someone's computer, named by its install) or a self-hosted one (named by the person). Only
the org's are offered or taken (the rrotors its people own, as row-level security shows them; a local one whose
install was signed out is gone). `linked` is whether it holds its link to Glyphh right now (its state, set at its
hello and its link's close, ops/link/presence.py): a run of a bot on a rrotor is sent there over that link
(ops/bots/remote.py), refused while the rrotor is offline. A project runs on one of these places too.

A page of the platform reads some things from the machine itself, never through this server (the folders a bot may
be given, the crew's work): `url` is where the browser finds the rrotor (a self-hosted one's own address; a local
one's loopback, which answers only a browser on that same computer), and `ticket` what lets the signed-in person in
there: a work ticket for that one rrotor, signed as a licence key is and checked on the machine (rrotor's
rrotord/ticket.py), good for TICKET_SECONDS. This server neither carries nor keeps what the ticket opens."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import Install, Rrotor
from glyphh_server.ops import license_keys
from glyphh_server.ops.link.presence import ONLINE

CLOUD: str = "Glyphh cloud"
LOCAL: str = "Local rrotor"
LOCAL_URL: str = "http://127.0.0.1:7777"  # a local rrotor's API, on its own computer's loopback
NOT_ORGS: str = "That is not one of the org's rrotors: GET /v1/bots/places lists where its bots can run."
TICKET_SECONDS: int = 600
TICKET_KIND: str = "work"


class Place(BaseModel):
    id: uuid.UUID | None = Field(description="The rrotor's id; none for Glyphh cloud")
    name: str
    mode: Literal["cloud", "local", "self"] = Field(description="cloud (Glyphh's), local or self (self-hosted)")
    linked: bool = Field(description="It holds its link to Glyphh right now (Glyphh cloud always)")
    url: str | None = Field(
        None,
        description="Where a browser reads the machine itself (its folders, its work): a self-hosted rrotor's "
        "address, a local one's loopback (only from that computer); none for Glyphh cloud",
    )
    version: str | None = Field(None, description="The rrotor version it last said it runs; none for Glyphh cloud")


class Places(BaseModel):
    places: list[Place]


class Ticket(BaseModel):
    token: str = Field(description="Sent to the rrotor as Authorization: Bearer <token>")
    expires_in: int = Field(description="Seconds it is good for; ask for another after")
    url: str = Field(description="The rrotor's own address, where the browser sends it")


async def listing(conn: AsyncConnection) -> Places:
    """Glyphh cloud first, then the org's rrotors by name."""
    found = (
        select(
            *(Rrotor.id, Rrotor.mode, Rrotor.name, Rrotor.state, Rrotor.public_url, Rrotor.image_version),
            Install.name.label("device"),
        )
        .outerjoin(Install, Install.id == Rrotor.install_id)
        .where(Install.revoked_at.is_(None))
    )
    rrotors = [
        Place(
            id=r.id,
            name=r.name or r.device or LOCAL,
            mode=r.mode,
            linked=r.state == ONLINE,
            url=r.public_url or LOCAL_URL,
            version=r.image_version,
        )
        for r in await conn.execute(found)
    ]
    cloud = Place(id=None, name=CLOUD, mode="cloud", linked=True)
    return Places(places=[cloud, *sorted(rrotors, key=lambda p: (p.name.lower(), str(p.id)))])


async def one(conn: AsyncConnection, rrotor_id: uuid.UUID) -> Place:
    """One of the org's rrotors; Invalid for any other."""
    found = next((p for p in (await listing(conn)).places if p.id == rrotor_id), None)
    if found is None:
        raise Invalid(NOT_ORGS, reason="runs_on", runs_on=str(rrotor_id))
    return found


async def checked(conn: AsyncConnection, runs_on: uuid.UUID | None) -> uuid.UUID | None:
    """Where the bot is to run, refused unless it is Glyphh cloud or one of the org's rrotors."""
    if runs_on is not None:
        await one(conn, runs_on)
    return runs_on


async def ticket(
    conn: AsyncConnection, signing_key: Ed25519PrivateKey, user_id: uuid.UUID, rrotor_id: uuid.UUID
) -> Ticket:
    """A work ticket for the person and this one rrotor of the org's, for their browser to read the machine with."""
    place = await one(conn, rrotor_id)
    until = (datetime.now(UTC) + timedelta(seconds=TICKET_SECONDS)).replace(microsecond=0)
    payload: dict[str, object] = {
        "kind": TICKET_KIND,
        "runtime_id": str(rrotor_id),
        "sub": str(user_id),
        "expires_at": until.isoformat().replace("+00:00", "Z"),
    }
    assert place.url is not None  # a rrotor has an address
    return Ticket(token=license_keys.encode(signing_key, payload), expires_in=TICKET_SECONDS, url=place.url)
