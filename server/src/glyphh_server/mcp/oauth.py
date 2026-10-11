"""Glyphh as the OAuth authorization server for MCP hosts, on the MCP SDK's own spec routes
(metadata, authorize, token with PKCE, registration, revocation). This class only connects them to
Glyphh's tables. Every host is a public client: it proves itself with PKCE, never a stored secret."""

from typing import Any

from mcp.server.auth.provider import AccessToken, AuthorizationCode, AuthorizationParams, RefreshToken, TokenError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Unauthorized
from glyphh_server.ops.auth import codes, hosts, tokens
from glyphh_server.ops.auth.codes import Pending

SIGN_IN_PATH: str = "/auth/sign-in"


def _client_info(row: Any) -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id=row.client_id,
        client_name=row.name,
        redirect_uris=row.redirect_uris,
        token_endpoint_auth_method="none",
        grant_types=["authorization_code", "refresh_token"],
    )


def _oauth_token(issued: tokens.IssuedTokens) -> OAuthToken:
    return OAuthToken(
        access_token=issued.access_token, expires_in=issued.expires_in, refresh_token=issued.refresh_token
    )


class GlyphhOAuth:
    def __init__(self, engine: AsyncEngine, public_url: str, secret_key: str) -> None:
        self.engine, self.public_url, self.secret_key = engine, public_url.rstrip("/"), secret_key

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with self.engine.connect() as conn:
            row = await hosts.find(conn, client_id)
        return None if row is None else _client_info(row)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        client_info.token_endpoint_auth_method, client_info.client_secret = "none", None
        client_info.client_secret_expires_at = None
        async with self.engine.begin() as conn:
            await hosts.register(
                conn,
                client_info.client_id or "",
                client_info.client_name or "An app",
                [str(u) for u in client_info.redirect_uris or []],
            )

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        pending = Pending(
            client_id=client.client_id or "",
            redirect_uri=str(params.redirect_uri),
            code_challenge=params.code_challenge,
            state=params.state,
            scopes=params.scopes or [],
            resource=params.resource,
        )
        return codes.pending_link(self.secret_key, self.public_url + SIGN_IN_PATH, pending)

    async def load_authorization_code(self, client: OAuthClientInformationFull, code: str) -> AuthorizationCode | None:
        async with self.engine.connect() as conn:
            host = await hosts.find(conn, client.client_id or "")
            row = None if host is None else await codes.find(conn, host.id, code)
        if row is None:
            return None
        return AuthorizationCode(
            code=code,
            scopes=[],
            expires_at=row.expires_at.timestamp(),
            client_id=client.client_id or "",
            code_challenge=row.code_challenge,
            redirect_uri=row.redirect_uri,
            redirect_uri_provided_explicitly=True,
            subject=str(row.user_id),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, code: AuthorizationCode
    ) -> OAuthToken:
        # TokenError is frozen, so it is raised after the transaction closes, never through it.
        async with self.engine.begin() as conn:
            user_id = await codes.consume(conn, code.code)
            host = await hosts.find(conn, client.client_id or "")
            issued = None if user_id is None or host is None else await tokens.issue(conn, user_id, host.id)
        if issued is None:
            raise TokenError("invalid_grant", "This code was already used.")
        return _oauth_token(issued)

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        async with self.engine.connect() as conn:
            row = await tokens.find_refresh(conn, refresh_token)
        if row is None:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=client.client_id or "",
            scopes=[],
            expires_at=int(row.refresh_expires_at.timestamp()),
            subject=str(row.user_id),
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        try:
            async with self.engine.begin() as conn:
                issued = await tokens.rotate(conn, refresh_token.token)
        except Unauthorized as err:
            raise TokenError("invalid_grant", err.message) from err
        return _oauth_token(issued)

    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            async with self.engine.connect() as conn:
                who = await tokens.principal_for(conn, token)
        except Unauthorized:
            return None
        return AccessToken(
            token=token,
            client_id=who.host_client_id or "glyphh",
            scopes=[],
            subject=str(who.user_id),
            claims={"org_id": str(who.org_id), "role": who.role},
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        async with self.engine.begin() as conn:
            await tokens.revoke(conn, token.token)
