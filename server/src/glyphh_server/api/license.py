"""This install's signed license, and the public key the mod checks it with; and a self-hosted runtime's heartbeat,
answered with its licence."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.errors import Unauthorized
from glyphh_server.ops import heartbeat, license
from glyphh_server.ops.heartbeat import Beat, Renewed
from glyphh_server.ops.license import License, LicenseKey
from glyphh_server.ops.link.presence import Refused, bearer

router = APIRouter(prefix="/v1/license", tags=["account"])


@router.get("", operation_id="getLicense")
async def get_license(caller: Caller, conn: Conn, request: Request) -> License:
    """Plan, the account's limits, mods (each mod included, by slug, with its limits: a number, or null for
    unlimited) and expires_at (24 hours), signed with Ed25519 over the payload's canonical JSON (keys sorted at every
    level, no spaces, ASCII)."""
    return await license.license_for(conn, caller, request.app.state.license_key)


@router.get("/key", operation_id="getLicenseKey")
async def get_license_key(caller: Caller, request: Request) -> LicenseKey:
    """The Ed25519 public key, base64 of its raw 32 bytes."""
    return license.public_key(request.app.state.license_key)


@router.post("/verify", operation_id="verifyRuntimeLicence", response_model=Renewed)
async def verify(body: Beat, request: Request) -> Response:
    """A self-hosted runtime's heartbeat, its runtime token as auth: `{machine, licence_id, version, active_runs}`,
    answered with a fresh licence (`kind: heartbeat`, 24 hours, `grace_days: 14`). Kept: when it beat, the version,
    the runs and the machine hash; never the caller's address."""
    state = request.app.state
    try:
        renewed = await heartbeat.beat(
            state.engine, state.license_key, bearer(request.headers.get("authorization")), body
        )
    except Refused as err:
        raise Unauthorized(str(err)) from None
    return JSONResponse(renewed.model_dump(mode="json"), headers={"cache-control": "no-store"})
