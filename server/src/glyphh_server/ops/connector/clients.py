"""Knowing an OAuth client at the authorization and token endpoints. The only client is the platform's own, made at
every start (db/seed_clients.py): nothing registers one any more. Its secret is kept only as a hash."""

import hmac
import uuid

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import OAuthClient
from glyphh_server.ops.auth.secrets import hash_secret
from glyphh_server.ops.connector.errors import invalid_client

GRANT_TYPES: tuple[str, ...] = ("authorization_code", "refresh_token")


async def find(conn: AsyncConnection, client_id: str | None) -> Row | None:
    try:
        key = uuid.UUID(client_id or "")
    except ValueError:
        return None
    columns = (OAuthClient.id, OAuthClient.name, OAuthClient.redirect_uris, OAuthClient.grant_types)
    found = select(*columns, OAuthClient.auth_method, OAuthClient.secret_hash).where(OAuthClient.id == key)
    return (await conn.execute(found)).first()


async def authenticate(conn: AsyncConnection, client_id: str | None, secret: str | None) -> Row:
    """The client calling the token or revocation endpoint: a public one by its id, a confidential one by its id and
    secret (compared in constant time)."""
    client = await find(conn, client_id)
    if client is None:
        raise invalid_client()
    if client.secret_hash is not None and not hmac.compare_digest(client.secret_hash, hash_secret(secret or "")):
        raise invalid_client()
    return client
