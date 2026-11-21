"""The token endpoint's two grants: an authorization code (with PKCE) for a first pair of tokens, a refresh token for
the next (rotated). The client has authenticated already."""

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.ops.connector import codes, tokens
from glyphh_server.ops.connector.authorize import NOT_OURS, canonical, runtime_resource
from glyphh_server.ops.connector.clients import GRANT_TYPES
from glyphh_server.ops.connector.errors import OAuthError
from glyphh_server.ops.connector.tokens import TokenAnswer


async def check_resource(conn: AsyncConnection, settings: Settings, form: dict[str, str]) -> None:
    if "resource" not in form:
        return
    own = (canonical(settings.mcp_resource), canonical(settings.base_url))
    if canonical(form["resource"]) not in own and await runtime_resource(conn, form["resource"]) is None:
        raise OAuthError("invalid_target", NOT_OURS)


async def exchange(conn: AsyncConnection, settings: Settings, client: Row, form: dict[str, str]) -> TokenAnswer:
    grant = form.get("grant_type")
    if grant not in GRANT_TYPES:
        raise OAuthError("unsupported_grant_type", "grant_type is authorization_code or refresh_token.")
    if grant not in client.grant_types:
        raise OAuthError("unauthorized_client", f"This client didn't register for {grant}.")
    await check_resource(conn, settings, form)
    if grant == "authorization_code":
        return await codes.redeem(conn, client.id, form)
    return await tokens.refresh(conn, client.id, form.get("refresh_token", ""), form.get("scope"))
