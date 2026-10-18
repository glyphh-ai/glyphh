"""A self-hosted runtime's licence beyond its link. Every 24 hours, and at boot, rrotor sends its heartbeat with its
runtime token (`POST /v1/license/verify`): a hash of its machine, the licence it holds, its version and how many runs
are in progress, never an address, a prompt or anything of a model's. The answer is a fresh licence (24 hours, and
14 days' grace). The server keeps only when it beat, the version, the runs and the machine hash; the caller's address
is never kept or logged (obs/logs.py drops the server's access line for this path).

Air-gapped, it has no link and no heartbeat: the person issues it an offline licence of 1 to 365 days, as one token
(base64url of the licence's JSON) for its environment or its `/data/licence.token`, checked with no network."""

import logging
import uuid
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Forbidden
from glyphh_server.models import Rrotor
from glyphh_server.obs.logs import fields
from glyphh_server.ops import self_hosted
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.license import GRACE_DAYS, HEARTBEAT, OFFLINE, License, Stamp, as_token, sign_license
from glyphh_server.ops.link.presence import runtime_for

log = logging.getLogger("glyphh.runtime")

MAX_OFFLINE_DAYS: int = 365


class Beat(BaseModel):
    """Exactly what the heartbeat carries."""

    model_config = ConfigDict(extra="forbid")

    machine: str = Field(pattern=r"^[0-9a-f]{64}$", description="SHA-256 (hex) of the runtime id and its machine id")
    licence_id: uuid.UUID | None = Field(description="The licence it holds now; null for none")
    version: str = Field(min_length=1, max_length=64, description="The rrotor version")
    active_runs: int = Field(ge=0, le=1_000_000, description="Runs in progress")


class Renewed(BaseModel):
    licence: License


class OfflineAsk(BaseModel):
    days: int = Field(ge=1, le=MAX_OFFLINE_DAYS, description="How long it lasts, 1 to 365 days")


class Offline(BaseModel):
    token: str = Field(description="base64url of the licence's JSON {payload, signature}: RROTOR_LICENCE")
    expires_at: datetime = Field(description="When it expires; it is live 14 days past it")


async def beat(engine: AsyncEngine, key: Ed25519PrivateKey, token: str | None, body: Beat) -> Renewed:
    """The heartbeat recorded and answered with a fresh licence; only a self-hosted runtime sends one. A token that is
    not good raises Refused."""
    runtime = await runtime_for(engine, token)
    if runtime.mode != "self":
        raise Forbidden(
            "Only a self-hosted runtime sends a heartbeat; its link brings this one's licence.", reason="not_self"
        )
    async with engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        values = {"last_heartbeat_at": func.now(), "image_version": body.version, "active_runs": body.active_runs}
        await conn.execute(update(Rrotor).where(Rrotor.id == runtime.id).values(**values, machine_hash=body.machine))
        stamp = Stamp(runtime.id, HEARTBEAT, GRACE_DAYS)
        licence = await sign_license(conn, key, runtime.user_id, runtime.org_id, None, stamp)
    return Renewed(licence=licence)


async def offline(
    conn: AsyncConnection, key: Ed25519PrivateKey, who: Principal, runtime_id: uuid.UUID, days: int
) -> Offline:
    """A long-lived licence for one of the person's self-hosted runtimes, as one token."""
    await self_hosted.mine(conn, who, runtime_id)
    stamp = Stamp(runtime_id, OFFLINE, GRACE_DAYS, timedelta(days=days))
    licence = await sign_license(conn, key, who.user_id, who.org_id, None, stamp)
    log.info(
        "offline licence issued",
        extra=fields(runtime=str(runtime_id), licence=str(licence.payload.licence_id), days=days),
    )
    return Offline(token=as_token(licence), expires_at=licence.payload.expires_at)
