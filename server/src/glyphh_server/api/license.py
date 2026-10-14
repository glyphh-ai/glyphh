"""This install's signed license, and the public key the mod checks it with."""

from fastapi import APIRouter, Request

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import license
from glyphh_server.ops.license import License, LicenseKey

router = APIRouter(prefix="/v1/license", tags=["account"])


@router.get("", operation_id="getLicense")
async def get_license(caller: Caller, conn: Conn, request: Request) -> License:
    """Plan, limits, mods (the slugs included, sorted) and expires_at (24 hours), signed with Ed25519 over the
    payload's canonical JSON (keys sorted, no spaces, ASCII)."""
    return await license.license_for(conn, caller, request.app.state.license_key)


@router.get("/key", operation_id="getLicenseKey")
async def get_license_key(caller: Caller, request: Request) -> LicenseKey:
    """The Ed25519 public key, base64 of its raw 32 bytes."""
    return license.public_key(request.app.state.license_key)
