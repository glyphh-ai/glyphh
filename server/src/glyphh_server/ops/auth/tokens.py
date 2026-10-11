"""The server's own tokens: a short access token and a longer refresh token, both kept only as hashes.
A refresh rotates: the old pair is revoked and a new pair issued, so a stolen refresh token works once."""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Unauthorized
from glyphh_server.models import OAuthClient, Token, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret

ACCESS_TTL: timedelta = timedelta(hours=1)
REFRESH_TTL: timedelta = timedelta(days=30)


class IssuedTokens(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


async def issue(conn: AsyncConnection, user_id: uuid.UUID, oauth_client_id: uuid.UUID | None = None) -> IssuedTokens:
    access, refresh, now = make_secret(), make_secret(), datetime.now(UTC)
    await conn.execute(
        insert(Token).values(
            user_id=user_id,
            oauth_client_id=oauth_client_id,
            access_hash=hash_secret(access),
            refresh_hash=hash_secret(refresh),
            access_expires_at=now + ACCESS_TTL,
            refresh_expires_at=now + REFRESH_TTL,
        )
    )
    return IssuedTokens(access_token=access, refresh_token=refresh, expires_in=int(ACCESS_TTL.total_seconds()))


async def principal_for(conn: AsyncConnection, access_token: str) -> Principal:
    """Who an access token belongs to. Anything wrong with it (unknown, expired, revoked) is one answer."""
    row = (
        await conn.execute(
            select(Token.user_id, Token.oauth_client_id, OAuthClient.client_id, User.org_id, User.role)
            .join(User, User.id == Token.user_id)
            .outerjoin(OAuthClient, OAuthClient.id == Token.oauth_client_id)
            .where(Token.access_hash == hash_secret(access_token))
            .where(Token.revoked_at.is_(None))
            .where(Token.access_expires_at > datetime.now(UTC))
            .where(User.disabled_at.is_(None))
        )
    ).first()
    if row is None:
        raise Unauthorized("Sign in again: this token is not valid.")
    return Principal(
        user_id=row.user_id,
        org_id=row.org_id,
        role=row.role,
        oauth_client_id=row.oauth_client_id,
        host_client_id=row.client_id,
    )


async def rotate(conn: AsyncConnection, refresh_token: str) -> IssuedTokens:
    """Trade a refresh token for a new pair; the old pair stops working at once."""
    row = (
        await conn.execute(
            update(Token)
            .where(Token.refresh_hash == hash_secret(refresh_token))
            .where(Token.revoked_at.is_(None))
            .where(Token.refresh_expires_at > datetime.now(UTC))
            .values(revoked_at=datetime.now(UTC))
            .returning(Token.user_id, Token.oauth_client_id)
        )
    ).first()
    if row is None:
        raise Unauthorized("Sign in again: this refresh token is not valid.")
    return await issue(conn, row.user_id, row.oauth_client_id)


async def revoke(conn: AsyncConnection, token: str) -> None:
    """Revoke the pair a token (access or refresh) belongs to. An unknown token is already as good as revoked."""
    digest = hash_secret(token)
    await conn.execute(
        update(Token)
        .where((Token.access_hash == digest) | (Token.refresh_hash == digest))
        .where(Token.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def find_refresh(conn: AsyncConnection, refresh_token: str) -> Token | None:
    row = (
        await conn.execute(
            select(Token).where(
                Token.refresh_hash == hash_secret(refresh_token),
                Token.revoked_at.is_(None),
                Token.refresh_expires_at > datetime.now(UTC),
            )
        )
    ).first()
    return None if row is None else Token(**row._mapping)
