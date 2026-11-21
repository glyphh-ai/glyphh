"""The platform signs in as an OAuth client: its access token works on /v1 as its person, sign-out ends its grant, and
it reads a consent from the browser with CORS for its own origin only."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api.browser_session import same_site
from glyphh_server.models import ConnectorGrant
from tests.conftest import PROVIDER_SETTINGS, SETTINGS
from tests.connector import ask, granted, register, to_allow
from tests.db.helpers import person

PLATFORM: str = SETTINGS.platform_base


async def test_v1_takes_an_oauth_access_token_as_its_person(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    me = await client.get("/v1/me", headers=auth)
    assert me.status_code == 200, me.text
    assert me.json()["email"] == ada.email
    assert (await client.get("/v1/org", headers=auth)).json()["id"] == str(ada.org_id)


async def test_an_access_token_for_another_resource_is_refused_like_any_bad_token(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    _, auth = await granted(engine, await person(engine), resource="https://elsewhere.example/mcp")
    res = await client.get("/v1/me", headers=auth)
    assert res.status_code == 401
    assert res.json()["error"]["message"] == "Sign in to Glyphh again: this token is not valid."


async def test_an_install_token_still_works(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    assert (await client.get("/v1/me", headers=ada.headers)).status_code == 200


async def test_signing_out_with_an_access_token_ends_its_grant(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    grant_id, auth = await granted(engine, ada)
    assert (await client.post("/v1/sign-out", headers=auth)).status_code == 204
    assert (await client.get("/v1/me", headers=auth)).status_code == 401
    async with engine.begin() as conn:
        ended = (await conn.execute(select(ConnectorGrant.revoked_at).where(ConnectorGrant.id == grant_id))).scalar()
    assert ended is not None
    assert (await client.get("/v1/me", headers=ada.headers)).status_code == 200


async def test_no_install_is_current_for_an_access_token(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    installs = (await client.get("/v1/installs", headers=auth)).json()
    assert [i["id"] for i in installs] == [str(ada.install_id)]
    assert installs[0]["current"] is False


async def test_a_local_runtime_needs_an_install(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    _, auth = await granted(engine, await person(engine))
    res = await client.post("/v1/runtime/local", headers=auth)
    assert res.status_code == 422
    assert res.json()["error"]["reason"] == "no_install"


async def _consent(client: httpx.AsyncClient) -> str:
    _, consent = await to_allow(client, ask(await register(client)))
    return consent


async def test_the_platform_reads_a_consent_with_credentials(client: httpx.AsyncClient) -> None:
    consent = await _consent(client)
    res = await client.get("/auth/consent", params={"consent": consent}, headers={"origin": PLATFORM})
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == PLATFORM
    assert res.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in res.headers["vary"]


async def test_a_refusal_carries_cors_too_so_the_platform_can_show_it(client: httpx.AsyncClient) -> None:
    client.cookies.clear()
    res = await client.get("/auth/consent", params={"consent": "x"}, headers={"origin": f"{PLATFORM}/"})
    assert res.status_code == 422
    assert res.headers["access-control-allow-origin"] == PLATFORM


async def test_no_other_origin_or_path_gets_cors(client: httpx.AsyncClient) -> None:
    consent = await _consent(client)
    other = await client.get("/auth/consent", params={"consent": consent}, headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
    assert "Origin" in other.headers["vary"]
    elsewhere = await client.get("/auth/providers", headers={"origin": PLATFORM})
    assert "access-control-allow-origin" not in elsewhere.headers


def test_the_signin_cookie_is_lax_on_one_site_and_none_across_sites() -> None:
    assert same_site(SETTINGS) == "lax"
    same = PROVIDER_SETTINGS.model_copy(
        update={"public_url": "https://api.glyphh.ai", "platform_url": "https://platform.glyphh.ai"}
    )
    assert same_site(same) == "lax"
    across = same.model_copy(update={"platform_url": "http://localhost:5173"})
    assert same_site(across) == "none"


async def test_the_cookie_is_sent_with_the_samesite_it_needs(engine: AsyncEngine) -> None:
    from glyphh_server.app import create_app
    from tests.conftest import _client
    from tests.fakes import fake_http

    across = PROVIDER_SETTINGS.model_copy(
        update={"public_url": "https://tunnel.example.dev", "platform_url": "http://localhost:5173"}
    )
    async for c in _client(create_app(across, http=fake_http())):
        q = ask(await register(c), resource=None)
        started = await c.get("/oauth/authorize", params=q)
        oauth = dict(httpx.URL(started.headers["location"]).params)["oauth"]
        res = await c.get("/auth/google/start", params={"oauth": oauth})
        cookie = res.headers["set-cookie"].lower()
        assert "samesite=none" in cookie and "secure" in cookie
