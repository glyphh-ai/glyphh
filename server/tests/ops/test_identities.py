"""Linking, past the pages: a person who is gone by the time the provider answers is refused."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid
from glyphh_server.ops.auth.signin import ProviderProfile
from glyphh_server.ops.identities import attach


async def test_linking_to_a_person_who_is_gone_is_refused(engine: AsyncEngine) -> None:
    profile = ProviderProfile(provider="github", subject=f"gh-{uuid.uuid4()}", email="x@gh.test", email_verified=True)
    async with engine.begin() as conn:
        with pytest.raises(Invalid, match="no longer valid"):
            await attach(conn, uuid.uuid4(), profile)
