"""This install's signed license, and the public key the mod checks it with; the org's licence keys and its runtime
nodes, for the platform to show; and a self-hosted runtime's heartbeat, answered with its licence and the org's
newest licence key."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.errors import Unauthorized
from glyphh_server.ops import heartbeat, license, license_keys, nodes
from glyphh_server.ops.heartbeat import Beat, Renewed
from glyphh_server.ops.license import License, LicenseKey
from glyphh_server.ops.license_keys import Keys
from glyphh_server.ops.link.presence import Refused, bearer
from glyphh_server.ops.nodes import Nodes

router = APIRouter(prefix="/v1/license", tags=["account"])


@router.get("", operation_id="getLicense")
async def get_license(caller: Caller, conn: Conn, request: Request) -> License:
    """Plan, the account's limits, mods (each mod included, by slug, with its limits: a number, or null for
    unlimited) and expires_at (24 hours), signed with Ed25519 over the payload's canonical JSON (keys sorted at every
    level, no spaces, ASCII)."""
    return await license.license_for(conn, caller, request.app.state.signing_key)


@router.get("/key", operation_id="getLicenseKey")
async def get_license_key(caller: Caller, request: Request) -> LicenseKey:
    """The Ed25519 public key, base64 of its raw 32 bytes."""
    return license.public_key(request.app.state.signing_key)


@router.get("/keys", operation_id="listLicenseKeys")
async def list_license_keys(caller: Caller, conn: Conn) -> Keys:
    """The org's licence keys, newest first, each in full with its terms and state (live, expired, revoked), and
    `license_key`, the newest live one: what its runtimes are sent, to show and copy for a node's
    `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key`. One per paid period, none on Free."""
    return await license_keys.keys(conn, caller.org_id)


@router.get("/nodes", operation_id="listRuntimeNodes")
async def list_runtime_nodes(caller: Caller, conn: Conn) -> Nodes:
    """The org's runtime nodes as their heartbeats and links say them, counted against the plan's (soft: `over` is
    shown, nothing is refused)."""
    return await nodes.nodes(conn, caller.org_id)


@router.post("/verify", operation_id="verifyRuntimeLicence", response_model=Renewed)
async def verify(body: Beat, request: Request) -> Response:
    """A self-hosted runtime's heartbeat, its runtime token as auth: `{machine, licence_id, version, active_runs}` and,
    from rrotor's clusters on, `{node_id, cluster_id, role, precedents}`, answered with a fresh licence (`kind:
    heartbeat`, 24 hours, `grace_days: 14`) and `license_key`, the org's newest licence key or null. Kept: when it
    beat, the version, the runs, the machine hash, the precedents and the node; never the caller's address."""
    state = request.app.state
    try:
        renewed = await heartbeat.beat(
            state.engine, state.signing_key, bearer(request.headers.get("authorization")), body
        )
    except Refused as err:
        raise Unauthorized(str(err)) from None
    return JSONResponse(renewed.model_dump(mode="json"), headers={"cache-control": "no-store"})
