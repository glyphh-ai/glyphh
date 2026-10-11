import os
from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from glyphh_server.app import create_app
from glyphh_server.config import Settings

DATABASE_URL: str = os.environ.get("GLYPHH_DATABASE_URL", "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh")
UNREACHABLE_URL: str = "postgresql+asyncpg://glyphh:glyphh@127.0.0.1:1/glyphh"


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(Settings(database_url=DATABASE_URL, version="test"))):
        yield c


@pytest.fixture
async def client_without_database() -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(Settings(database_url=UNREACHABLE_URL, version="test"))):
        yield c
