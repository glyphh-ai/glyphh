"""rrotor shelved (his ruling, 2026-11-02): with GLYPHH_RROTOR off, as the server ships, the connector neither lists nor
calls rrotor's tools (runtime keys, self-hosted runtimes, offline licences, apps), its instructions name the account
and Ada only, and the apps panel is not among its resources."""

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.mcp import panel
from glyphh_server.mcp.tools.registry import RROTOR
from tests.conftest import SETTINGS, _client
from tests.connector import granted, rpc
from tests.db.helpers import person
from tests.fakes import fake_http

SHELVED = SETTINGS.model_copy(update={"rrotor": False})


def test_rrotor_is_off_by_default() -> None:
    assert Settings(_env_file=None).rrotor is False  # type: ignore[call-arg]


async def test_the_shelved_connector_offers_the_account_alone(engine: AsyncEngine) -> None:
    _, auth = await granted(engine, await person(engine))
    async for c in _client(create_app(SHELVED, http=fake_http())):
        listed = {t["name"] for t in (await rpc(c, auth, "tools/list"))["result"]["tools"]}
        assert "whoami" in listed
        assert listed.isdisjoint(RROTOR)
        for name in ("apps", "app_approve", "self_runtimes", "runtime_keys", "offline_licence"):
            assert name in RROTOR
            assert (await rpc(c, auth, "tools/call", name=name, arguments={}))["error"]["code"] == -32602
        said = (await rpc(c, auth, "server/discover"))["result"]["instructions"]
        assert "rrotor" not in said and "runtime" not in said and "app_approve" not in said
        uris = {r["uri"] for r in (await rpc(c, auth, "resources/list"))["result"]["resources"]}
        assert panel.URI in uris and panel.APPS_URI not in uris


async def test_shown_the_connector_offers_rrotors_tools(engine: AsyncEngine) -> None:
    _, auth = await granted(engine, await person(engine))
    async for c in _client(create_app(SETTINGS, http=fake_http())):
        listed = {t["name"] for t in (await rpc(c, auth, "tools/list"))["result"]["tools"]}
        assert set(RROTOR) <= listed
        assert "app_approve" in (await rpc(c, auth, "server/discover"))["result"]["instructions"]
