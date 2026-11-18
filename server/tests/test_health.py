import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from tests.conftest import SETTINGS, UNREACHABLE_REDIS, _client


async def test_the_api_reports_ok_with_the_database_up(client: httpx.AsyncClient) -> None:
    res = await client.get("/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "test", "database": True, "redis": True}


async def test_the_api_reports_degraded_without_the_database(client_without_database: httpx.AsyncClient) -> None:
    res = await client_without_database.get("/v1/health")
    assert res.json() == {"status": "degraded", "version": "test", "database": False, "redis": False}


async def test_the_api_reports_degraded_without_redis(engine: AsyncEngine) -> None:
    app = create_app(SETTINGS.model_copy(update={"redis_url": UNREACHABLE_REDIS}))
    async for client in _client(app):
        res = await client.get("/v1/health")
        assert res.json() == {"status": "degraded", "version": "test", "database": True, "redis": False}
