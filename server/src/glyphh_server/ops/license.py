"""The license: what an install's plan allows (the account's limits, and each mod the org has, from its plan or an
add-on, with that mod's limits), signed with Ed25519 so the mod can check it offline with the public key, and
short-lived so a change of plan or add-ons reaches the machine within a day. docs/architecture.md (The license) shows
the payload.

The signature is over the payload's canonical JSON: keys sorted, no spaces, ASCII only (json.dumps with
sort_keys=True, separators=(",", ":")). That is what the mod rebuilds from `payload` to verify it.

A runtime's licence also says which runtime it is for, its own id, and how it came: `link` (a welcome), `heartbeat`
(a self-hosted runtime's daily call) or `offline` (issued for an air-gapped one, up to a year). A self-hosted
runtime's licence counts as live for `grace_days` past `expires_at`. An install's licence has none of these."""

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.ops.addons import licensed
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.plans import Limits, ModLimits, org_plan

LICENSE_TTL: timedelta = timedelta(hours=24)
GRACE_DAYS: int = 14  # a self-hosted runtime's licence: live this long past expires_at
LINK, HEARTBEAT, OFFLINE = "link", "heartbeat", "offline"


def _absent(value: object) -> bool:
    return value is None


class LicensePayload(BaseModel):
    install_id: uuid.UUID | None  # none for a hosted runtime's licence: no install starts it
    user_id: uuid.UUID
    org_id: uuid.UUID
    plan: str
    limits: Limits
    mods: dict[str, ModLimits]
    expires_at: datetime
    runtime_id: uuid.UUID | None = Field(None, exclude_if=_absent)  # a runtime's licence: which
    licence_id: uuid.UUID | None = Field(None, exclude_if=_absent)
    kind: str | None = Field(None, exclude_if=_absent, description="link, heartbeat or offline")
    grace_days: int | None = Field(None, exclude_if=_absent, description="Days it holds past expires_at; absent, 0")


@dataclass(frozen=True, slots=True)
class Stamp:
    """What a runtime's licence says of itself: the runtime, how it came, its grace and how long it lasts."""

    runtime_id: uuid.UUID
    kind: str
    grace_days: int | None = None
    ttl: timedelta = LICENSE_TTL


class License(BaseModel):
    payload: LicensePayload
    signature: str


class LicenseKey(BaseModel):
    alg: str = "Ed25519"
    public_key: str


def load_key(settings: Settings) -> Ed25519PrivateKey:
    """The configured key; outside prod, without one, a new key for this run."""
    if settings.license_key:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(settings.license_key))
    if settings.env == "prod":
        raise RuntimeError("GLYPHH_LICENSE_KEY must be set in prod: base64 of a raw 32-byte Ed25519 private key.")
    return Ed25519PrivateKey.generate()


def canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


async def license_for(conn: AsyncConnection, who: Principal, key: Ed25519PrivateKey) -> License:
    return await sign_license(conn, key, who.user_id, who.org_id, who.install_id)


async def sign_license(
    conn: AsyncConnection,
    key: Ed25519PrivateKey,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    install_id: uuid.UUID | None,
    stamp: Stamp | None = None,
) -> License:
    plan = await org_plan(conn, org_id)
    mods = plan.mods | await licensed(conn, org_id, plan.name)
    own: dict[str, Any] = {}
    if stamp is not None:
        own = {
            "runtime_id": stamp.runtime_id,
            "licence_id": uuid.uuid4(),
            "kind": stamp.kind,
            "grace_days": stamp.grace_days,
        }
    payload = LicensePayload(
        install_id=install_id,
        user_id=user_id,
        org_id=org_id,
        plan=plan.name,
        limits=plan.limits,
        mods=dict(sorted(mods.items())),
        expires_at=datetime.now(UTC).replace(microsecond=0) + (stamp.ttl if stamp else LICENSE_TTL),
        **own,
    )
    signature = key.sign(canonical(payload.model_dump(mode="json")))
    return License(payload=payload, signature=base64.b64encode(signature).decode())


def public_key(key: Ed25519PrivateKey) -> LicenseKey:
    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return LicenseKey(public_key=base64.b64encode(raw).decode())


def as_token(licence: License) -> str:
    """A licence as one string, for an air-gapped runtime's environment or file: base64url (padded) of its JSON
    `{payload, signature}`."""
    raw = json.dumps(licence.model_dump(mode="json"), separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode()
