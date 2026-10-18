"""The platform's OAuth client: made at start from the settings, under the platform's id, and good at the token
endpoint with its secret; kept true to the settings on every start; nothing without them."""

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.schema import apply_schema
from glyphh_server.models import OAuthClient
from glyphh_server.ops.connector.clients import authenticate
from tests.conftest import SETTINGS

CLIENT_ID = str(uuid.uuid4())


async def _client(engine: AsyncEngine) -> tuple[str, list[str]] | None:
    async with engine.connect() as conn:
        found = select(OAuthClient.name, OAuthClient.redirect_uris).where(OAuthClient.id == uuid.UUID(CLIENT_ID))
        row = (await conn.execute(found)).first()
    return None if row is None else (row.name, list(row.redirect_uris))


async def _forget(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(delete(OAuthClient).where(OAuthClient.id == uuid.UUID(CLIENT_ID)))


async def test_the_platform_client_is_made_from_the_settings_and_its_secret_works(engine: AsyncEngine) -> None:
    settings = SETTINGS.model_copy(
        update={"platform_client_id": CLIENT_ID, "platform_client_secret": "s1", "platform_url": "https://p.test/"}
    )
    await apply_schema(engine, settings)
    assert await _client(engine) == ("Glyphh", ["https://p.test/auth/callback"])
    async with engine.connect() as conn:
        assert (await authenticate(conn, CLIENT_ID, "s1")).id == uuid.UUID(CLIENT_ID)
    await apply_schema(engine, settings.model_copy(update={"platform_client_secret": "s2"}))  # a new secret takes
    async with engine.connect() as conn:
        assert (await authenticate(conn, CLIENT_ID, "s2")).id == uuid.UUID(CLIENT_ID)
    await _forget(engine)


async def test_without_the_settings_no_client_is_made(engine: AsyncEngine) -> None:
    await apply_schema(engine, SETTINGS.model_copy(update={"platform_client_id": CLIENT_ID}))
    assert await _client(engine) is None


async def test_an_id_that_is_not_a_uuid_stops_the_start(engine: AsyncEngine) -> None:
    bad = SETTINGS.model_copy(update={"platform_client_id": "not-a-uuid", "platform_client_secret": "s"})
    with pytest.raises(RuntimeError, match="must be a UUID"):
        await apply_schema(engine, bad)
