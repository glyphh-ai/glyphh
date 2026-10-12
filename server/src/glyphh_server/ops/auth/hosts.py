"""Agent hosts (Claude, Codex, ...): registered once, then connected per member by signing in.
A member sees the hosts they connected and can disconnect one without touching the others."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import OAuthClient, Token

# The platform is Glyphh itself, never a connected host (ops/auth/platform.py).
PLATFORM: str = "glyphh-platform"


class Host(BaseModel):
    id: uuid.UUID
    name: str
    connected_at: datetime


async def register(conn: AsyncConnection, client_id: str, name: str, redirect_uris: list[str]) -> None:
    await conn.execute(insert(OAuthClient).values(client_id=client_id, name=name, redirect_uris=redirect_uris))


async def find(conn: AsyncConnection, client_id: str) -> OAuthClient | None:
    row = (await conn.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))).first()
    return None if row is None else OAuthClient(**row._mapping)


async def connected(conn: AsyncConnection, user_id: uuid.UUID) -> list[Host]:
    rows = await conn.execute(
        select(OAuthClient.id, OAuthClient.name, func.min(Token.created_at).label("connected_at"))
        .join(Token, Token.oauth_client_id == OAuthClient.id)
        .where(Token.user_id == user_id, Token.revoked_at.is_(None), OAuthClient.client_id != PLATFORM)
        .group_by(OAuthClient.id, OAuthClient.name)
        .order_by(OAuthClient.name)
    )
    return [Host(id=r.id, name=r.name, connected_at=r.connected_at) for r in rows]


async def disconnect(conn: AsyncConnection, user_id: uuid.UUID, host_id: uuid.UUID) -> None:
    ended = await conn.execute(
        update(Token)
        .where(Token.user_id == user_id, Token.oauth_client_id == host_id, Token.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    if ended.rowcount == 0:
        raise NotFound("That host is not connected to your Glyphh.", host_id=str(host_id))
