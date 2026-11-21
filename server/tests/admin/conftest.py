"""The staff view under test: an app whose staff is one fresh email and whose platform client is made in the database,
a staff member signed in through it, and the ways to sign in as anyone else."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import OAuthClient
from glyphh_server.ops.connector import grants, tokens
from tests.conftest import PROVIDER_SETTINGS, _client
from tests.connector import RESOURCE
from tests.db.helpers import Person, person
from tests.fakes import FakeStripe, fake_http

PLATFORM_ID: uuid.UUID = uuid.UUID("0f0f0f0f-0000-4000-8000-00000000a0a0")


async def platform_headers(engine: AsyncEngine, who: Person) -> dict[str, str]:
    """An access token of the platform's own OAuth client, as the platform holds one after its sign-in."""
    async with engine.begin() as conn:
        values = {"name": "Glyphh", "redirect_uris": ["http://localhost:3000/auth/callback"]}
        values |= {"auth_method": "client_secret_basic", "secret_hash": "x", "grant_types": ["authorization_code"]}
        await conn.execute(upsert(OAuthClient).values(id=PLATFORM_ID, **values).on_conflict_do_nothing())
        grant_id = await grants.grant_for(conn, who.user_id, PLATFORM_ID, "account", RESOURCE)
        answer = await tokens.issue(conn, grant_id, "account")
    return {"authorization": f"Bearer {answer.access_token}"}


@dataclass
class Admin:
    http: httpx.AsyncClient
    staff: Person
    headers: dict[str, str]
    stripe: FakeStripe

    async def get(self, path: str, **params: object) -> httpx.Response:
        return await self.http.get(f"/v1/admin{path}", params=params, headers=self.headers)  # type: ignore[arg-type]


@pytest.fixture
async def admin(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Admin]:
    email = f"staff-{uuid.uuid4().hex[:10]}@glyphh.test"
    settings = PROVIDER_SETTINGS.model_copy(
        update={"staff_emails": f"nobody@glyphh.test, {email.upper()}", "platform_client_id": str(PLATFORM_ID)}
    )
    staff = await person(engine, email=email)
    headers = await platform_headers(engine, staff)
    async for http in _client(create_app(settings, http=fake_http(stripe))):
        yield Admin(http, staff, headers, stripe)
