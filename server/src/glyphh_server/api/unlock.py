"""A mod bought once, per machine (Drips, Games): its licence, by the mod's own install id, once Stripe has said the
Payment Link's checkout is paid. Open: the install id is the only key, and the licence is for that install alone."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from glyphh_server.api.auth import Conn
from glyphh_server.ops import unlock
from glyphh_server.ops.unlock import UnlockLicence

router = APIRouter(prefix="/v1/unlock", tags=["unlock"])

Install = Annotated[str, Query(min_length=1, max_length=200)]
Mod = Annotated[str, Query(min_length=1, max_length=40)]


@router.get("/license", operation_id="getUnlockLicence")
async def get_unlock_licence(mod: Mod, install: Install, conn: Conn, request: Request) -> UnlockLicence:
    """`paid` false until the mod's Payment Link checkout for this install is paid; then the licence,
    `base64url(payload).base64url(Ed25519 signature)`, checked with `GET /v1/license/key`."""
    return await unlock.licence_for(conn, request.app.state.license_key, mod, install)
