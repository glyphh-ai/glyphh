"""/mcp, the Glyphh connector (Streamable HTTP, stateless): POST only, one JSON-RPC message per request, each answered
with one JSON object. A browser Origin other than the server's own or the allowed ones is refused (DNS rebinding);
the bearer must be a connector access token issued for this resource, and the request then runs as its person, in
their org."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.errors import error_body
from glyphh_server.api.oauth_meta import resource_metadata_url
from glyphh_server.db import tenancy
from glyphh_server.mcp import protocol, server
from glyphh_server.mcp.protocol import INVALID_REQUEST, RpcError
from glyphh_server.mcp.tools.base import Context
from glyphh_server.obs import context
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.connector import tokens
from glyphh_server.ops.connector.authorize import SCOPE

router = APIRouter(tags=["connector"])


def challenge(request: Request, token_sent: bool) -> JSONResponse:
    """401, naming the resource metadata so the client can find where to sign in (RFC 9728 section 5.1)."""
    value = f'Bearer resource_metadata="{resource_metadata_url(request)}", scope="{SCOPE}"'
    if token_sent:
        value += ', error="invalid_token"'
    message = "Sign in to Glyphh: connect the Glyphh connector again." if token_sent else "Sign in to Glyphh."
    return JSONResponse(error_body("E_UNAUTHORIZED", message), 401, headers={"www-authenticate": value})


def origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    settings = request.app.state.settings
    return origin is None or origin.rstrip("/") in {settings.base_url, *settings.mcp_origin_list}


async def caller(request: Request, conn: Conn) -> Principal | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    who = await tokens.principal_for(conn, token.strip(), request.app.state.settings.mcp_resource)
    if who is not None:
        context.user_id.set(str(who.user_id))
        context.org_id.set(str(who.org_id))
        await tenancy.enter(conn, who.org_id)
    return who


def rpc_refusal(err: RpcError) -> JSONResponse:
    return JSONResponse(protocol.failure(err), err.status)


@router.post("/mcp", operation_id="mcp", response_model=None)
async def mcp(request: Request, conn: Conn) -> Response:
    """The Glyphh connector: MCP 2026-07-28 and the earlier initialize revisions, with a connector access token."""
    if not origin_allowed(request):
        return rpc_refusal(RpcError(INVALID_REQUEST, "This origin may not call the Glyphh connector.", 403))
    who = await caller(request, conn)
    if who is None:
        return challenge(request, "authorization" in request.headers)
    try:
        call = protocol.read(await request.body(), request.headers)
    except RpcError as err:
        return rpc_refusal(err)
    if call.id is None:
        return Response(status_code=202)
    state = request.app.state
    ctx = Context(conn, who, state.settings, state.http, state.hub, state.license_key)
    try:
        result: dict[str, Any] = await server.handle(ctx, call)
    except RpcError as err:
        err.id = call.id
        return rpc_refusal(err)
    return JSONResponse(protocol.answer(call, result, server.server_info(ctx)))


@router.get("/mcp", include_in_schema=False)
@router.delete("/mcp", include_in_schema=False)
async def no_stream() -> Response:
    """No standalone stream and no sessions: only POST."""
    return Response(status_code=405, headers={"allow": "POST"})
