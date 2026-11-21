"""An install's bearer token: opaque, random, kept only as a hash. It stops working when it expires, when it is
revoked, or when its install is revoked."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Unauthorized
from glyphh_server.models import Install, Org, Token, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret

TOKEN_TTL: timedelta = timedelta(days=365)
SEEN_EVERY: timedelta = timedelta(minutes=1)


async def issue(conn: AsyncConnection, install_id: uuid.UUID) -> str:
    token = make_secret()
    await conn.execute(
        insert(Token).values(
            install_id=install_id, token_hash=hash_secret(token), expires_at=datetime.now(UTC) + TOKEN_TTL
        )
    )
    return token


async def principal_for(conn: AsyncConnection, token: str) -> Principal:
    """Who a token belongs to. Anything wrong with it (unknown, expired, revoked, its install revoked) is one
    answer. A good one marks its install seen."""
    row = (
        await conn.execute(
            select(Token.install_id, User.id, User.org_id, User.role, User.email, Org.suspended_at)
            .join(Install, Install.id == Token.install_id)
            .join(User, User.id == Install.user_id)
            .join(Org, Org.id == User.org_id)
            .where(
                Token.token_hash == hash_secret(token),
                Token.revoked_at.is_(None),
                Token.expires_at > func.now(),
                Install.revoked_at.is_(None),
            )
        )
    ).first()
    if row is None:
        raise Unauthorized("Sign in to Glyphh again: this token is not valid.")
    await conn.execute(
        update(Install)
        .where(
            Install.id == row.install_id,
            or_(Install.last_seen_at.is_(None), Install.last_seen_at < func.now() - SEEN_EVERY),
        )
        .values(last_seen_at=func.now())
    )
    suspended = row.suspended_at is not None
    return Principal(
        user_id=row.id,
        org_id=row.org_id,
        role=row.role,
        install_id=row.install_id,
        suspended=suspended,
        email=row.email,
    )


async def revoke_install(conn: AsyncConnection, install_id: uuid.UUID) -> None:
    """Sign that machine out: the install and every token it holds."""
    await conn.execute(
        update(Install).where(Install.id == install_id, Install.revoked_at.is_(None)).values(revoked_at=func.now())
    )
    await revoke_tokens(conn, install_id)


async def revoke_tokens(conn: AsyncConnection, install_id: uuid.UUID) -> None:
    """Every token the install holds stops working; the install stays."""
    await conn.execute(
        update(Token).where(Token.install_id == install_id, Token.revoked_at.is_(None)).values(revoked_at=func.now())
    )
