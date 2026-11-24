"""The connector's tokens: an access token (opaque, 1 hour) and a refresh token (30 days) per exchange, kept only as
hashes. A refresh token rotates on every use; one already used, presented again, means it was stolen or replayed, so
the whole grant is revoked (OAuth 2.1 section 4.3.1)."""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import Row, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import ConnectorGrant, ConnectorToken, Org, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.connector import grants
from glyphh_server.ops.connector.errors import OAuthError, invalid_grant

ACCESS_TTL: timedelta = timedelta(hours=1)
REFRESH_TTL: timedelta = timedelta(days=30)
SEEN_EVERY: timedelta = timedelta(minutes=1)


class TokenAnswer(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str


async def _token(conn: AsyncConnection, grant_id: uuid.UUID, kind: str, ttl: timedelta) -> str:
    token = make_secret()
    values = {
        "grant_id": grant_id,
        "kind": kind,
        "token_hash": hash_secret(token),
        "expires_at": datetime.now(UTC) + ttl,
    }
    await conn.execute(insert(ConnectorToken).values(values))
    return token


async def issue(conn: AsyncConnection, grant_id: uuid.UUID, scope: str) -> TokenAnswer:
    return TokenAnswer(
        access_token=await _token(conn, grant_id, "access", ACCESS_TTL),
        expires_in=int(ACCESS_TTL.total_seconds()),
        refresh_token=await _token(conn, grant_id, "refresh", REFRESH_TTL),
        scope=scope,
    )


async def _held(conn: AsyncConnection, token: str) -> Row | None:
    """A token and its grant, whatever their state, locked for this exchange."""
    found = (
        select(ConnectorToken.id, ConnectorToken.kind, ConnectorToken.grant_id, ConnectorToken.expires_at)
        .add_columns(ConnectorToken.used_at, ConnectorToken.revoked_at, ConnectorGrant.client_id, ConnectorGrant.scope)
        .add_columns(ConnectorGrant.resource, ConnectorGrant.revoked_at.label("grant_revoked_at"))
        .join(ConnectorGrant, ConnectorGrant.id == ConnectorToken.grant_id)
        .where(ConnectorToken.token_hash == hash_secret(token))
        .with_for_update(of=ConnectorToken)
    )
    return (await conn.execute(found)).first()


async def refresh(conn: AsyncConnection, client_id: uuid.UUID, token: str, scope: str | None) -> TokenAnswer:
    held = await _held(conn, token)
    if held is None or held.kind != "refresh" or held.client_id != client_id:
        raise invalid_grant("The refresh token is not valid.")
    if held.used_at is not None:
        await grants.end(conn, held.grant_id)
        raise invalid_grant("The refresh token was already used: the grant is revoked. Sign in again.")
    if held.revoked_at or held.grant_revoked_at or held.expires_at <= datetime.now(UTC):
        raise invalid_grant("The refresh token is not valid.")
    if scope is not None and not set(scope.split()) <= set(held.scope.split()):
        raise OAuthError("invalid_scope", "A refresh can't widen the scope.")
    await conn.execute(update(ConnectorToken).where(ConnectorToken.id == held.id).values(used_at=func.now()))
    return await issue(conn, held.grant_id, held.scope)


async def revoke(conn: AsyncConnection, client_id: uuid.UUID, token: str) -> None:
    """RFC 7009: a refresh token revokes its grant, an access token itself; a token unknown or another client's is
    left alone, and the answer is the same."""
    held = await _held(conn, token)
    if held is None or held.client_id != client_id:
        return
    if held.kind == "refresh":
        await grants.end(conn, held.grant_id)
    else:
        await conn.execute(update(ConnectorToken).where(ConnectorToken.id == held.id).values(revoked_at=func.now()))


async def _live(conn: AsyncConnection, token: str, resource: str) -> Row | None:
    """An access token issued for this resource, unexpired, not revoked, its grant live: who holds it. A good one
    marks its grant used."""
    row = (
        await conn.execute(
            select(ConnectorToken.grant_id, User.id, User.org_id, User.role)
            .add_columns(ConnectorGrant.client_id, User.email, Org.suspended_at)
            .join(ConnectorGrant, ConnectorGrant.id == ConnectorToken.grant_id)
            .join(User, User.id == ConnectorGrant.user_id)
            .join(Org, Org.id == User.org_id)
            .where(
                ConnectorToken.token_hash == hash_secret(token),
                ConnectorToken.kind == "access",
                ConnectorToken.revoked_at.is_(None),
                ConnectorToken.expires_at > func.now(),
                ConnectorGrant.revoked_at.is_(None),
                ConnectorGrant.resource == resource,
            )
        )
    ).first()
    if row is None:
        return None
    await conn.execute(
        update(ConnectorGrant)
        .where(
            ConnectorGrant.id == row.grant_id,
            or_(ConnectorGrant.last_used_at.is_(None), ConnectorGrant.last_used_at < func.now() - SEEN_EVERY),
        )
        .values(last_used_at=func.now())
    )
    return row


async def principal_for(conn: AsyncConnection, token: str, resource: str) -> Principal | None:
    """Who an access token on /mcp belongs to."""
    row = await _live(conn, token, resource)
    if row is None:
        return None
    return Principal(
        user_id=row.id,
        org_id=row.org_id,
        role=row.role,
        grant_id=row.grant_id,
        client_id=row.client_id,
        suspended=row.suspended_at is not None,
        email=row.email,
    )
