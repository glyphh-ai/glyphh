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


async def test_every_route_in_the_spec_has_an_operation_id_and_the_token_is_a_bearer(client: httpx.AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    ops = {(m, p): o.get("operationId") for p, v in spec["paths"].items() for m, o in v.items()}
    assert all(ops.values()) and len(set(ops.values())) == len(ops) == 129
    assert spec["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    assert "security" not in spec["paths"]["/v1/plans"]["get"]
    assert "security" not in spec["paths"]["/v1/mods"]["get"]
    assert spec["paths"]["/v1/me"]["get"]["security"] == [{"HTTPBearer": []}]


async def test_the_api_reports_degraded_without_redis(engine: AsyncEngine) -> None:
    app = create_app(SETTINGS.model_copy(update={"redis_url": UNREACHABLE_REDIS}))
    async for client in _client(app):
        res = await client.get("/v1/health")
        assert res.json() == {"status": "degraded", "version": "test", "database": True, "redis": False}
