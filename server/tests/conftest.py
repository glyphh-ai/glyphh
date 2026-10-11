import os
from collections.abc import AsyncIterator

import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.db import make_engine
from glyphh_server.schema import apply_schema

DATABASE_URL: str = os.environ.get(
    "GLYPHH_DATABASE_URL", "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh_test"
)
UNREACHABLE_URL: str = "postgresql+asyncpg://glyphh:glyphh@127.0.0.1:1/glyphh"


async def _fresh_database(url: str) -> None:
    """The suite owns its database: dropped and made again each run, never the dev data."""
    target = make_url(url)
    admin = await asyncpg.connect(
        host=target.host, port=target.port, user=target.username, password=target.password, database="postgres"
    )
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{target.database}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    await _fresh_database(DATABASE_URL)
    eng = make_engine(DATABASE_URL)
    await apply_schema(eng)
    yield eng
    await eng.dispose()


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(Settings(database_url=DATABASE_URL, version="test"))):
        yield c


@pytest.fixture
async def client_without_database() -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(Settings(database_url=UNREACHABLE_URL, version="test"))):
        yield c
