"""The staff view under test: an app whose staff are two fresh emails, one of them a person signed in through the
platform (as every person the helpers make is), the other free for a test to make a second staff member of."""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from tests.conftest import PLATFORM_ID, PROVIDER_SETTINGS, _client
from tests.db.helpers import Person, person
from tests.fakes import FakeStripe, fake_http

__all__ = ["PLATFORM_ID", "Admin"]


@dataclass
class Admin:
    http: httpx.AsyncClient
    staff: Person
    headers: dict[str, str]
    colleague: str  # another staff email, nobody's yet

    async def get(self, path: str, **params: object) -> httpx.Response:
        return await self.http.get(f"/v1/admin{path}", params=params, headers=self.headers)  # type: ignore[arg-type]

    async def post(self, path: str, json: object = None) -> httpx.Response:
        return await self.http.post(f"/v1/admin{path}", json=json, headers=self.headers)

    async def delete(self, path: str) -> httpx.Response:
        return await self.http.delete(f"/v1/admin{path}", headers=self.headers)


@pytest.fixture
async def admin(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Admin]:
    email = f"staff-{uuid.uuid4().hex[:10]}@glyphh.test"
    colleague = f"staff-{uuid.uuid4().hex[:10]}@glyphh.test"
    settings = PROVIDER_SETTINGS.model_copy(update={"staff_emails": f"{colleague}, {email.upper()}"})
    staff = await person(engine, email=email)
    async for http in _client(create_app(settings, http=fake_http(stripe))):
        yield Admin(http, staff, staff.headers, colleague)
