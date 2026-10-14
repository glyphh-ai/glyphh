"""The license: what an install's plan allows, signed with Ed25519 so the mod can check it offline with the public
key, and short-lived so a change of plan reaches the machine within a day.

The signature is over the payload's canonical JSON: keys sorted, no spaces, ASCII only (json.dumps with
sort_keys=True, separators=(",", ":")). That is what the mod rebuilds from `payload` to verify it."""

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.plans import Features, Limits, org_version, view

LICENSE_TTL: timedelta = timedelta(hours=24)


class LicensePayload(BaseModel):
    install_id: uuid.UUID
    user_id: uuid.UUID
    org_id: uuid.UUID
    plan: str
    limits: Limits
    features: Features
    expires_at: datetime


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
    plan = view(await org_version(conn, who.org_id))
    payload = LicensePayload(
        install_id=who.install_id,
        user_id=who.user_id,
        org_id=who.org_id,
        plan=plan.name,
        limits=plan.limits,
        features=plan.features,
        expires_at=datetime.now(UTC).replace(microsecond=0) + LICENSE_TTL,
    )
    signature = key.sign(canonical(payload.model_dump(mode="json")))
    return License(payload=payload, signature=base64.b64encode(signature).decode())


def public_key(key: Ed25519PrivateKey) -> LicenseKey:
    raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return LicenseKey(public_key=base64.b64encode(raw).decode())
