"""The connector's authorization server endpoints a model calls: registering a client (RFC 7591), the token
endpoint (authorization code with PKCE, refresh with rotation) and revocation (RFC 7009). Their refusals are OAuth's
own shape, answered (not raised) so what a refusal revokes is kept."""

import base64
import binascii
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.wound_down import platform_only
from glyphh_server.ops.connector import clients, exchange, tokens
from glyphh_server.ops.connector.errors import OAuthError, invalid_client

router = APIRouter(prefix="/oauth", tags=["connector"])

NO_STORE: dict[str, str] = {"cache-control": "no-store", "pragma": "no-cache"}


def refusal(err: OAuthError, basic: bool = False) -> JSONResponse:
    headers = dict(NO_STORE)
    if err.status == 401 and basic:
        headers["www-authenticate"] = 'Basic realm="glyphh"'
    return JSONResponse({"error": err.error, "error_description": err.description}, err.status, headers=headers)


async def read_form(request: Request) -> dict[str, str]:
    return {k: v for k, v in (await request.form()).items() if isinstance(v, str)}


def is_basic(request: Request) -> bool:
    return request.headers.get("authorization", "").lower().startswith("basic ")


def credentials(request: Request, form: dict[str, str]) -> tuple[str | None, str | None]:
    """The client's id and secret: HTTP Basic (each form-encoded, RFC 6749 section 2.3.1) or the form's."""
    if not is_basic(request):
        return form.get("client_id"), form.get("client_secret")
    try:
        raw = base64.b64decode(request.headers["authorization"][6:], validate=True).decode()
    except (binascii.Error, UnicodeDecodeError) as err:
        raise invalid_client() from err
    client_id, _, secret = raw.partition(":")
    return unquote(client_id), unquote(secret)


@router.post("/register", operation_id="registerOAuthClient", status_code=201, response_model=None)
async def register(request: Request, conn: Conn) -> Response:
    """Register an MCP client: its redirect URIs (https, or http on localhost), name and how it authenticates."""
    try:
        body: Any = await request.json()
    except ValueError:
        return refusal(OAuthError("invalid_client_metadata", "The body must be JSON client metadata."))
    try:
        made = await clients.register(conn, body)
    except OAuthError as err:
        return refusal(err)
    return JSONResponse(made.model_dump(exclude_none=True), 201, headers=NO_STORE)


@router.post("/token", operation_id="oauthToken", response_model=None)
async def token(request: Request, conn: Conn) -> Response:
    """Exchange an authorization code (with its PKCE verifier) or a refresh token for an access token (1 hour) and a
    new refresh token (30 days)."""
    form = await read_form(request)
    try:
        client = await clients.authenticate(conn, *credentials(request, form))
        platform_only(request.app.state.settings, client.id)  # wound down: a connector's client gets 410
        answer = await exchange.exchange(conn, request.app.state.settings, client, form)
    except OAuthError as err:
        return refusal(err, is_basic(request))
    return JSONResponse(answer.model_dump(), headers=NO_STORE)


@router.post("/revoke", operation_id="oauthRevoke", response_model=None)
async def revoke(request: Request, conn: Conn) -> Response:
    """Revoke a token: a refresh token ends its grant, an access token itself. Answers 200 for any token."""
    form = await read_form(request)
    try:
        client = await clients.authenticate(conn, *credentials(request, form))
    except OAuthError as err:
        return refusal(err, is_basic(request))
    await tokens.revoke(conn, client.id, form.get("token", ""))
    return Response(status_code=200, headers=NO_STORE)
