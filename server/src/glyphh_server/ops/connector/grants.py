"""Connector grants: each client a person allowed, one live grant per person and client (allowing it again reuses
it), revocable one by one from the account or the connector. Revoking a grant ends every token it holds."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import ConnectorGrant, ConnectorToken, OAuthClient
from glyphh_server.ops.auth.principal import Principal


class GrantView(BaseModel):
    id: uuid.UUID
    client: str
    scope: str
    created_at: datetime
    last_used_at: datetime | None
    current: bool


async def grant_for(
    conn: AsyncConnection, user_id: uuid.UUID, client_id: uuid.UUID, scope: str, resource: str
) -> uuid.UUID:
    """The person's live grant for this client, made the first time."""
    made = (
        upsert(ConnectorGrant)
        .values(user_id=user_id, client_id=client_id, scope=scope, resource=resource)
        .on_conflict_do_update(
            index_elements=[ConnectorGrant.user_id, ConnectorGrant.client_id],
            index_where=ConnectorGrant.revoked_at.is_(None),
            set_={"scope": scope, "resource": resource},
        )
        .returning(ConnectorGrant.id)
    )
    return (await conn.execute(made)).scalar_one()


async def end(conn: AsyncConnection, grant_id: uuid.UUID) -> None:
    """The grant is revoked, and every token it holds with it."""
    await conn.execute(
        update(ConnectorGrant)
        .where(ConnectorGrant.id == grant_id, ConnectorGrant.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )
    await conn.execute(
        update(ConnectorToken)
        .where(ConnectorToken.grant_id == grant_id, ConnectorToken.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )


async def list_grants(conn: AsyncConnection, who: Principal) -> list[GrantView]:
    rows = await conn.execute(
        select(
            ConnectorGrant.id,
            OAuthClient.name.label("client"),
            ConnectorGrant.scope,
            ConnectorGrant.created_at,
            ConnectorGrant.last_used_at,
        )
        .join(OAuthClient, OAuthClient.id == ConnectorGrant.client_id)
        .where(ConnectorGrant.user_id == who.user_id, ConnectorGrant.revoked_at.is_(None))
        .order_by(ConnectorGrant.created_at)
    )
    return [GrantView(**r._mapping, current=r.id == who.grant_id) for r in rows]


async def revoke(conn: AsyncConnection, who: Principal, grant_id: uuid.UUID) -> None:
    mine = select(ConnectorGrant.id).where(
        ConnectorGrant.id == grant_id, ConnectorGrant.user_id == who.user_id, ConnectorGrant.revoked_at.is_(None)
    )
    if (await conn.execute(mine)).first() is None:
        raise NotFound("You have no such connector grant.", grant_id=str(grant_id))
    await end(conn, grant_id)
