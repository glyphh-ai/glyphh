"""A mod bought once, per machine, with no Glyphh account: Glyphh Drip. The mod opens the mod's Stripe Payment
Link with its own install id as `client_reference_id`; Stripe's `checkout.session.completed` (the link's metadata
naming the mod) records the purchase; the mod then fetches its licence by mod and install, and checks it offline
with the server's public key (`GET /v1/license/key`) from then on.

The licence is `base64url(payload) "." base64url(signature)`: the payload `{"v": 1, "mod", "install", "session",
"issued"}` as compact JSON, the Ed25519 signature over the first part's text. A refund (`charge.refunded`) marks the
purchase refunded, and the licence is no longer handed out."""

import base64
import json
import logging
from datetime import UTC, datetime
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import UNLOCK_MODS, Unlock
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.unlock")


class UnlockLicence(BaseModel):
    paid: bool
    licence: str | None = None


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def licence_text(key: Ed25519PrivateKey, mod: str, install: str, session_id: str, issued: datetime) -> str:
    payload = {"v": 1, "mod": mod, "install": install, "session": session_id, "issued": issued.isoformat()}
    first = _b64url(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return f"{first}.{_b64url(key.sign(first.encode()))}"


def check_mod(mod: str) -> str:
    if mod not in UNLOCK_MODS:
        raise Invalid("No such mod is sold once.", mod=mod, reason="no_mod")
    return mod


async def record_checkout(conn: AsyncConnection, obj: dict[str, Any]) -> bool:
    """A finished one-time checkout: its mod from the Payment Link's metadata, its install from the reference. A
    session seen before, an unpaid one, or one for no mod of ours changes nothing."""
    mod, install, session_id = obj.get("metadata", {}).get("mod"), obj.get("client_reference_id"), obj.get("id")
    if mod not in UNLOCK_MODS or not install or not session_id or obj.get("payment_status") != "paid":
        log.info("checkout not an unlock", extra=fields(session=session_id, mod=mod))
        return False
    row = {"session_id": session_id, "mod": mod, "install": install, "payment_intent_id": obj.get("payment_intent")}
    await conn.execute(insert(Unlock).values(**row).on_conflict_do_nothing(index_elements=[Unlock.session_id]))
    return True


async def record_refund(conn: AsyncConnection, obj: dict[str, Any]) -> None:
    """A refunded charge: the purchase its payment intent made is marked refunded; a charge of no purchase of ours
    changes nothing."""
    intent = obj.get("payment_intent")
    if intent:
        await conn.execute(
            update(Unlock)
            .where(Unlock.payment_intent_id == intent, Unlock.refunded_at.is_(None))
            .values(refunded_at=datetime.now(UTC))
        )


async def licence_for(conn: AsyncConnection, key: Ed25519PrivateKey, mod: str, install: str) -> UnlockLicence:
    """The licence for this mod on this install, from its latest purchase not refunded; `paid` false until then."""
    row = (
        await conn.execute(
            select(Unlock.session_id, Unlock.paid_at)
            .where(Unlock.mod == check_mod(mod), Unlock.install == install, Unlock.refunded_at.is_(None))
            .order_by(Unlock.paid_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return UnlockLicence(paid=False)
    return UnlockLicence(paid=True, licence=licence_text(key, mod, install, row.session_id, row.paid_at))
