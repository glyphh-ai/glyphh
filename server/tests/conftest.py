import os
from collections.abc import AsyncIterator

import asyncpg
import httpx
import pytest
from asgi_lifespan import LifespanManager
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.schema import apply_schema
from glyphh_server.db.signals import make_redis
from tests.fakes import FakeGitHubApp, FakeStripe, fake_http

# The suite tests the products as built, so their switch is on here, for every Settings a test makes and every worker
# process it starts; wound down, the default (GLYPHH_PRODUCTS off), is tests/api/test_wound_down.py's.
os.environ["GLYPHH_PRODUCTS"] = "on"

# The suite's database is made by the superuser in GLYPHH_DATABASE_URL and owned by an ordinary role the server
# connects as: a superuser bypasses row-level security, so only an ordinary role proves the tenant policies hold.
ADMIN_URL: str = os.environ.get("GLYPHH_DATABASE_URL", "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh_test")
APP_ROLE: str = "glyphh_app"
DATABASE_URL: str = make_url(ADMIN_URL).set(username=APP_ROLE, password=APP_ROLE).render_as_string(hide_password=False)
UNREACHABLE_URL: str = "postgresql+asyncpg://glyphh:glyphh@127.0.0.1:1/glyphh"
# A real Redis: the test profile's own database on the compose service; pub/sub channels are per person.
REDIS_URL: str = os.environ.get("GLYPHH_REDIS_URL", "redis://localhost:6379/1")
UNREACHABLE_REDIS: str = "redis://127.0.0.1:1/0"
SECRET_KEY: str = "test-secret-key-that-signs-sign-in-links-0123456789"
PUBLIC_URL: str = "http://localhost:8080"
WEBHOOK_SECRET: str = "whsec_test_not_a_real_secret"
GITHUB_APP_ID: str = "424242"
GITHUB_APP_KEY: rsa.RSAPrivateKey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
GITHUB_APP_PEM: str = GITHUB_APP_KEY.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()
SETTINGS: Settings = Settings(
    env="test",
    # rrotor's connector tools as they are when shown (the default); tests/api/test_mcp_shelved.py covers them off.
    rrotor=True,
    database_url=DATABASE_URL,
    redis_url=REDIS_URL,
    version="test",
    public_url=PUBLIC_URL,
    secret_key=SECRET_KEY,
    stripe_secret_key="sk_test_not_a_real_key",
    stripe_webhook_secret=WEBHOOK_SECRET,
    stripe_price_basic="price_test_basic",
    stripe_price_pro="price_test_pro",
    stripe_price_team="price_test_team",
    github_app_id=GITHUB_APP_ID,
    github_app_private_key=GITHUB_APP_PEM,
    github_app_slug="glyphh-test",
)
PROVIDER_SETTINGS: Settings = SETTINGS.model_copy(
    update={
        "google_client_id": "g-client",
        "google_client_secret": "g-secret",
        "github_client_id": "gh-client",
        "github_client_secret": "gh-secret",
    }
)


async def _fresh_database(url: str) -> None:
    """The suite owns its database: dropped and made again each run, never the dev data, owned by the app's role."""
    target = make_url(url)
    admin = await asyncpg.connect(
        host=target.host, port=target.port, user=target.username, password=target.password, database="postgres"
    )
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)')
        if not await admin.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", APP_ROLE):
            await admin.execute(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_ROLE}'")
        await admin.execute(f'CREATE DATABASE "{target.database}" OWNER {APP_ROLE}')
    finally:
        await admin.close()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    await _fresh_database(ADMIN_URL)
    eng = make_engine(DATABASE_URL)
    await apply_schema(eng, SETTINGS)
    yield eng
    await eng.dispose()


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = make_redis(REDIS_URL)
    yield client
    await client.aclose()


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def stripe() -> FakeStripe:
    return FakeStripe()


@pytest.fixture
def github_app() -> FakeGitHubApp:
    return FakeGitHubApp(GITHUB_APP_KEY.public_key(), GITHUB_APP_ID)


@pytest.fixture
async def client(
    engine: AsyncEngine, stripe: FakeStripe, github_app: FakeGitHubApp
) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(PROVIDER_SETTINGS, http=fake_http(stripe, github_app=github_app))):
        yield c


@pytest.fixture
async def client_without_database() -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(
        create_app(
            Settings(database_url=UNREACHABLE_URL, redis_url=UNREACHABLE_REDIS, version="test", secret_key=SECRET_KEY)
        )
    ):
        yield c
