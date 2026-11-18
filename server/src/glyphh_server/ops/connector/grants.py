"""Grants: a person's sign-in through an OAuth client (the platform's), one live grant per person and client (signing
in again reuses it). Ending a grant ends every token it holds."""

import uuid

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import ConnectorGrant, ConnectorToken


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
