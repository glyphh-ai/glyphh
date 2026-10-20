"""The platform's own OAuth client, made at every start from the server's settings, so a reset of the database
(db/reset.py) never loses it as it would a client registered once (POST /oauth/register). Kept
under the id the platform already holds, with its secret's hash and its one redirect URI, `{platform}/auth/callback`;
a changed secret or address takes on the next start. Without the settings, nothing is made."""

import uuid

from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import OAuthClient
from glyphh_server.ops.auth.secrets import hash_secret
from glyphh_server.ops.connector.clients import GRANT_TYPES

PLATFORM_CLIENT_NAME: str = "Glyphh"  # the name the platform recognises its own consent screens by


async def seed_platform_client(conn: AsyncConnection, settings: Settings) -> None:
    if not settings.platform_client_id or not settings.platform_client_secret:
        return
    try:
        client_id = uuid.UUID(settings.platform_client_id)
    except ValueError as err:
        raise RuntimeError("GLYPHH_PLATFORM_CLIENT_ID must be a UUID: the platform's PLATFORM_CLIENT_ID.") from err
    values = {
        "name": PLATFORM_CLIENT_NAME,
        "redirect_uris": [f"{settings.platform_url.rstrip('/')}/auth/callback"],
        "auth_method": "client_secret_basic",
        "secret_hash": hash_secret(settings.platform_client_secret),
        "grant_types": list(GRANT_TYPES),
    }
    made = upsert(OAuthClient).values(id=client_id, **values)
    await conn.execute(made.on_conflict_do_update(index_elements=[OAuthClient.id], set_=values))
