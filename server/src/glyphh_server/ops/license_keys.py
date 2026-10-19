"""The licence key (rrotor's docs/specs/licensing.md): one string, `<base64url payload>.<base64url signature>`
without padding, the payload UTF-8 JSON and the signature Ed25519 over the payload's exact bytes, with the server's
signing key (GLYPHH_LICENSE_SIGNING_KEY; the public key is in rrotor's code). rrotor checks it on the node with no
network and holds the newest good one.

The payload is the org's plan as signed now: `tier` the plan's name in lower case, `max_nodes` its runtime nodes,
`max_precedents` its precedents per node, `cluster_sync_enabled` its sync; `customer_id` the org's id (no name or
address). One is issued for each paid period, expiring at its end (ops/billing/webhook.py), and for an Enterprise
grant, through its last day (ops/enterprise.py); never on Free, which is rrotor's default with no key (Community).
Each is kept in `licenses`. Delivered: the org's newest live key (not revoked, not expired) in the link's `welcome`
and the heartbeat's answer, and to the platform (`GET /v1/license/keys`); the connector shows it masked."""

import base64
import json
import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, Field
from sqlalchemy import Row, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.seed import FREE
from glyphh_server.models import LicenseRecord
from glyphh_server.ops.plans import org_version

NAMES: tuple[str, ...] = ("tier", "max_nodes", "max_precedents", "cluster_sync_enabled")
TERMS = (
    LicenseRecord.tier,
    LicenseRecord.max_nodes,
    LicenseRecord.max_precedents,
    LicenseRecord.cluster_sync_enabled,
)


class KeyView(BaseModel):
    license_id: uuid.UUID
    tier: str = Field(description="free, pro, team or enterprise")
    max_nodes: int | None = Field(description="Nodes one cluster may have; null = unlimited")
    max_precedents: int | None = Field(description="Precedents one node may hold, across its models; null = unlimited")
    cluster_sync_enabled: bool
    issued_at: datetime
    expires_at: datetime = Field(description="rrotor holds it 14 days past this, then runs as Community")
    revoked_at: datetime | None = Field(description="When it stopped being delivered: its subscription or grant ended")
    state: str = Field(description="live, expired or revoked")
    key: str = Field(description="The key: GLYPHH_LICENSE_KEY or /etc/rrotor/license.key on a node")


class Keys(BaseModel):
    license_key: str | None = Field(description="The org's newest live key, what rrotor is sent; null: none (Free)")
    keys: list[KeyView] = Field(description="Every key issued to the org, newest first")


def rfc3339(at: datetime) -> str:
    """UTC to the second, `Z`: as rrotor reads it."""
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def encode(signing_key: Ed25519PrivateKey, payload: dict[str, object]) -> str:
    """The key string: the payload's bytes as signed, then the signature over exactly them."""
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return f"{b64url(raw)}.{b64url(signing_key.sign(raw))}"


def masked(key: str | None) -> str | None:
    """Enough of a key to tell it apart, never enough to use: its first 8 and last 6 characters."""
    return None if key is None else f"{key[:8]}…{key[-6:]}"


async def issue(
    conn: AsyncConnection, signing_key: Ed25519PrivateKey, org_id: uuid.UUID, expires_at: datetime
) -> str | None:
    """A key for the org's plan as it is now, expiring then; none on Free. The same terms to the same expiry already
    live (an event delivered twice, a checkout and its first invoice) is that key again, not another."""
    plan = await org_version(conn, org_id)
    if plan.name == FREE:
        return None
    terms = dict(zip(NAMES, (plan.name.lower(), plan.max_machines, plan.precedents, plan.sync), strict=True))
    expires_at = expires_at.astimezone(UTC).replace(microsecond=0)
    same = await conn.execute(
        select(LicenseRecord.key, *TERMS).where(
            LicenseRecord.org_id == org_id,
            LicenseRecord.revoked_at.is_(None),
            LicenseRecord.expires_at == expires_at,
        )
    )
    found = next((r.key for r in same if tuple(r[1:]) == tuple(terms.values())), None)
    if found is not None:
        return found
    license_id, issued_at = uuid.uuid4(), datetime.now(UTC).replace(microsecond=0)
    payload = {
        "license_id": str(license_id),
        **terms,
        "issued_at": rfc3339(issued_at),
        "expires_at": rfc3339(expires_at),
        "customer_id": str(org_id),
    }
    key = encode(signing_key, payload)
    times = {"issued_at": issued_at, "expires_at": expires_at}
    await conn.execute(
        insert(LicenseRecord).values(id=license_id, org_id=org_id, **terms, **times, customer_id=str(org_id), key=key)
    )
    return key


async def revoke(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    """Every key of the org's no longer delivered: its subscription or grant ended. A node holding one keeps it to its
    expiry and grace; no fresh one follows."""
    live = (LicenseRecord.org_id == org_id, LicenseRecord.revoked_at.is_(None))
    await conn.execute(update(LicenseRecord).where(*live).values(revoked_at=func.now()))


async def newest(conn: AsyncConnection, org_id: uuid.UUID) -> str | None:
    """The org's newest live key: latest issued_at, ties to the later expires_at, as rrotor picks."""
    found = (
        select(LicenseRecord.key)
        .where(
            LicenseRecord.org_id == org_id,
            LicenseRecord.revoked_at.is_(None),
            LicenseRecord.expires_at > func.now(),
        )
        .order_by(LicenseRecord.issued_at.desc(), LicenseRecord.expires_at.desc())
        .limit(1)
    )
    return (await conn.execute(found)).scalar_one_or_none()


def _view(row: Row, now: datetime) -> KeyView:
    state = "revoked" if row.revoked_at else "expired" if row.expires_at <= now else "live"
    return KeyView(license_id=row.id, state=state, **{k: v for k, v in row._mapping.items() if k != "id"})


async def keys(conn: AsyncConnection, org_id: uuid.UUID) -> Keys:
    found = (
        select(LicenseRecord.id, *TERMS, LicenseRecord.issued_at, LicenseRecord.expires_at)
        .add_columns(LicenseRecord.revoked_at, LicenseRecord.key)
        .where(LicenseRecord.org_id == org_id)
        .order_by(LicenseRecord.issued_at.desc(), LicenseRecord.expires_at.desc())
    )
    now = datetime.now(UTC)
    return Keys(license_key=await newest(conn, org_id), keys=[_view(r, now) for r in await conn.execute(found)])
