"""Who may call the Ada API, at which host: API keys made by a signed-in person, a Glyphh sign-in, nothing else; and
with GLYPHH_ADA_CLOUD off, no Ada at all."""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.api import HostRouter, auth
from glyphh_ada.process import Worker
from glyphh_server.app import create_app
from glyphh_server.models import RuntimeKey
from tests.ada.conftest import a_model, an_org, key_for
from tests.conftest import SETTINGS, _client
from tests.db.helpers import person


async def test_keys_are_made_listed_and_revoked_by_a_person(
    engine: AsyncEngine, ada: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, worker: Worker
) -> None:
    monkeypatch.setattr(auth, "KEY_TTL", 0.0)
    who = await person(engine, "Team")
    made = await ada.post(
        "/v1/keys", json={"name": "ci", "clearance": 0.25, "expires_in_days": 30}, headers=who.headers
    )
    key = made.json()
    assert key["key"].startswith("glyphh_ak_") and key["clearance"] == 0.25 and key["expires_at"]
    bearer = {"authorization": f"Bearer {key['key']}"}
    assert (await ada.get("/v1/models", headers=bearer)).status_code == 200
    assert (await ada.get("/v1/keys", headers=bearer)).status_code == 401  # a key does not make keys
    listed = (await ada.get("/v1/keys", headers=who.headers)).json()
    assert [k["name"] for k in listed] == ["ci"] and "key" not in listed[0]
    runtime = await ada.get("/v1/runtime/keys", headers=who.headers)  # the Ada host is not the account API
    assert runtime.status_code == 404
    revoked = await ada.delete(f"/v1/keys/{key['id']}", headers=who.headers)
    assert revoked.json()["revoked_at"]
    assert (await ada.delete(f"/v1/keys/{key['id']}", headers=who.headers)).status_code == 404
    gone = await ada.get("/v1/models", headers=bearer)
    assert (gone.status_code, gone.json()["error"]["code"]) == (401, "E_AUTH")


async def test_a_key_is_deleted_only_once_it_no_longer_works(
    engine: AsyncEngine, ada: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, worker: Worker
) -> None:
    monkeypatch.setattr(auth, "KEY_TTL", 0.0)
    who = await person(engine, "Team")
    other = await person(engine, "Team")
    live = (await ada.post("/v1/keys", json={"name": "live"}, headers=who.headers)).json()
    old = (await ada.post("/v1/keys", json={"name": "old"}, headers=who.headers)).json()
    late = (await ada.post("/v1/keys", json={"name": "late", "expires_in_days": 1}, headers=who.headers)).json()

    refused = await ada.delete(f"/v1/keys/{live['id']}/forever", headers=who.headers)
    assert (refused.status_code, refused.json()["error"]["code"]) == (409, "E_CONFLICT")  # revoke it first

    await ada.delete(f"/v1/keys/{old['id']}", headers=who.headers)
    stranger = await ada.delete(f"/v1/keys/{old['id']}/forever", headers=other.headers)
    assert stranger.status_code == 404  # only its maker deletes it
    bearer = {"authorization": f"Bearer {old['key']}"}
    assert (await ada.delete(f"/v1/keys/{old['id']}/forever", headers=bearer)).status_code == 401  # never by a key
    assert (await ada.delete(f"/v1/keys/{old['id']}/forever", headers=who.headers)).status_code == 204
    assert (await ada.delete(f"/v1/keys/{old['id']}/forever", headers=who.headers)).status_code == 404

    async with engine.begin() as conn:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        await conn.execute(update(RuntimeKey).where(RuntimeKey.name == "late").values(expires_at=past))
    assert (await ada.delete(f"/v1/keys/{late['id']}/forever", headers=who.headers)).status_code == 204  # expired

    listed = (await ada.get("/v1/keys", headers=who.headers)).json()
    assert [k["name"] for k in listed] == ["live"]


async def test_an_expired_or_wrong_key_or_none_is_401(
    engine: AsyncEngine, ada: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, worker: Worker
) -> None:
    monkeypatch.setattr(auth, "KEY_TTL", 0.0)
    who, key = await an_org(engine, ada)
    async with engine.begin() as conn:
        await conn.execute(update(RuntimeKey).where(RuntimeKey.scope == "cloud").values(expires_at=None))
    assert (await ada.get("/v1/models", headers=key)).status_code == 200
    async with engine.begin() as conn:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        await conn.execute(update(RuntimeKey).where(RuntimeKey.user_id == who.user_id).values(expires_at=past))
    for headers in (key, {"authorization": "Bearer glyphh_ak_nope"}, {"authorization": "Bearer nope"}, {}):
        refused = await ada.get("/v1/models", headers=headers)
        assert (refused.status_code, refused.json()["error"]["code"]) == (401, "E_AUTH")


async def test_a_sign_in_calls_with_full_clearance_and_keys_are_kept_briefly(
    engine: AsyncEngine, ada: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, worker: Worker
) -> None:
    monkeypatch.setattr(auth, "KEPT_MAX", 1)
    who, key = await an_org(engine, ada)
    await a_model(ada, who.headers)  # a person signed in makes and reads models too
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["name"] == "shapes"
    assert (await ada.get("/v1/models/shapes", headers=key)).status_code == 200  # from the cache
    other = await key_for(ada, who)
    assert (await ada.get("/v1/models", headers=other)).status_code == 200  # the cache is full: emptied first


async def test_cloud_keys_are_never_a_runtimes(engine: AsyncEngine, client: httpx.AsyncClient) -> None:
    who = await person(engine, "Team")
    async with engine.begin() as conn:
        await conn.execute(
            RuntimeKey.__table__.insert().values(user_id=who.user_id, name="cloud", key_hash="h1", scope="cloud")
        )
    assert (await client.get("/v1/runtime/keys", headers=who.headers)).json() == []


async def test_with_ada_cloud_off_no_host_reaches_it(engine: AsyncEngine) -> None:
    app = create_app(SETTINGS)
    assert not any(m.cls is HostRouter for m in app.user_middleware)
    async for c in _client(app):
        c.base_url = httpx.URL("http://ada.glyphh.ai")
        assert (await c.post("/v1/decide", json={})).status_code == 404  # the account API's answer
        assert (await c.get("/v1/models")).status_code == 404  # the account API has no models of its own
        assert (await c.get("/v1/me")).status_code == 401  # the account API's own route, signed in


async def test_the_ada_hosts_and_only_they_reach_it(engine: AsyncEngine, ada: httpx.AsyncClient) -> None:
    assert (await ada.post("/v1/decide", json={})).status_code == 401  # ada.test: Ada's refusal
    for url in ("http://other.test:8443", "http://ADA.TEST"):
        refused = await ada.post(f"{url}/v1/decide", json={})
        assert refused.json()["error"]["code"] == "E_AUTH"
    api = await ada.post("http://api.test/v1/decide", json={})
    assert api.status_code == 404
    health = await ada.get("/v1/health")
    assert health.status_code == 200 and health.json()["database"]
