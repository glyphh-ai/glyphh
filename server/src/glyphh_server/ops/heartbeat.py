"""A self-hosted runtime's licence beyond its link. Every 24 hours, and at boot, rrotor sends its heartbeat with its
runtime token (`POST /v1/license/verify`): a hash of its machine, the licence it holds, its version and how many runs
are in progress, and, from rrotor's clusters on, which node it is (`node_id`, `cluster_id`, `role`) and its store's
precedents; never an address, a prompt or anything of a model's. The answer is a fresh licence (24 hours, and 14
days' grace) and, beside it, the org's newest licence key (ops/license_keys.py), or null: rrotor N reads both and
prefers the key. The server keeps only when it beat, the version, the runs, the machine hash, the precedents and the
node (ops/nodes.py); the caller's address is never kept or logged (obs/logs.py drops the server's access line for
this path).

Air-gapped, it has no link and no heartbeat: on Enterprise, the person issues it an offline licence of 1 to 365
days, as one token (base64url of the licence's JSON) for its environment or its `/data/licence.token`, checked with
no network."""

import logging
import uuid
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.db.seed import SALES
from glyphh_server.errors import Forbidden, NotInPlan
from glyphh_server.models import Rrotor
from glyphh_server.obs.logs import fields
from glyphh_server.ops import license_keys, nodes, self_hosted
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.license import GRACE_DAYS, HEARTBEAT, OFFLINE, License, Stamp, as_token, sign_license
from glyphh_server.ops.link.presence import runtime_for
from glyphh_server.ops.plans import org_version

log = logging.getLogger("glyphh.runtime")

MAX_OFFLINE_DAYS: int = 365


class Beat(BaseModel):
    """Exactly what the heartbeat carries."""

    model_config = ConfigDict(extra="forbid")

    machine: str = Field(pattern=r"^[0-9a-f]{64}$", description="SHA-256 (hex) of the runtime id and its machine id")
    licence_id: uuid.UUID | None = Field(description="The licence it holds now; null for none")
    version: str = Field(min_length=1, max_length=64, description="The rrotor version")
    active_runs: int = Field(ge=0, le=1_000_000, description="Runs in progress")
    node_id: nodes.NodeId | None = None
    cluster_id: uuid.UUID | None = Field(None, description="Its cluster; null when standalone")
    role: nodes.Role | None = None
    precedents: int | None = Field(None, ge=0, description="This node's store: precedents across its models")


class Renewed(BaseModel):
    licence: License = Field(description="Today's licence, until rrotor N+1 drops it")
    license_key: str | None = Field(description="The org's newest licence key; null: none (Community)")


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
        await _keep(conn, runtime.id, body)
        stamp = Stamp(runtime.id, HEARTBEAT, GRACE_DAYS)
        licence = await sign_license(conn, key, runtime.user_id, runtime.org_id, None, stamp)
        return Renewed(licence=licence, license_key=await license_keys.newest(conn, runtime.org_id))


async def _keep(conn: AsyncConnection, runtime_id: uuid.UUID, body: Beat) -> None:
    values = {"last_heartbeat_at": func.now(), "image_version": body.version, "active_runs": body.active_runs}
    if body.precedents is not None:
        values |= {"precedents": body.precedents, "precedents_at": func.now()}
    await conn.execute(update(Rrotor).where(Rrotor.id == runtime_id).values(**values, machine_hash=body.machine))
    if body.node_id is not None:
        said = {
            "cluster_id": body.cluster_id,
            "role": body.role,
            "precedents": body.precedents,
            "version": body.version,
        }
        await nodes.record(conn, runtime_id, body.node_id, said)


async def offline(
    conn: AsyncConnection, key: Ed25519PrivateKey, who: Principal, runtime_id: uuid.UUID, days: int
) -> Offline:
    """A long-lived licence for one of the person's self-hosted runtimes, as one token: on a plan with offline
    licences (Enterprise) only."""
    await self_hosted.mine(conn, who, runtime_id)
    plan = await org_version(conn, who.org_id)
    if not plan.offline:
        raise NotInPlan(
            f"Offline licences are on Enterprise, not {plan.name}: talk to us at {SALES}.", reason="offline"
        )
    stamp = Stamp(runtime_id, OFFLINE, GRACE_DAYS, timedelta(days=days))
    licence = await sign_license(conn, key, who.user_id, who.org_id, None, stamp)
    log.info(
        "offline licence issued",
        extra=fields(runtime=str(runtime_id), licence=str(licence.payload.licence_id), days=days),
    )
    return Offline(token=as_token(licence), expires_at=licence.payload.expires_at)
