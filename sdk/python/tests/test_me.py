import os
from datetime import datetime

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh, GlyphhError, Host, Me, MeOrg

SERVER: str = os.environ.get("GLYPHH_URL") or "http://localhost:8080"

ME: dict = {
    "id": "7f0c7b1e-0000-4000-8000-000000000001",
    "email": "ada@acme.test",
    "first_name": "Ada",
    "last_name": None,
    "image_url": None,
    "role": "org_admin",
    "org": {"id": "7f0c7b1e-0000-4000-8000-000000000002", "name": "Acme", "plan": "Free"},
}
HOST: dict = {
    "id": "7f0c7b1e-0000-4000-8000-000000000003",
    "name": "Claude Code",
    "connected_at": "2026-10-11T12:00:00Z",
}


def answering(status: int, body: object = None, seen: list | None = None) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status) if body is None else httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


def test_me_without_a_token_is_refused_with_the_servers_code_and_trace() -> None:
    with pytest.raises(GlyphhError) as e:
        Glyphh(SERVER).me()
    assert (e.value.status, e.value.code) == (401, "E_UNAUTHORIZED")
    assert e.value.trace_id and "Sign in" in str(e.value)


async def test_async_me_without_a_token_is_refused_the_same() -> None:
    with pytest.raises(GlyphhError) as e:
        await AsyncGlyphh(SERVER).me()
    assert e.value.code == "E_UNAUTHORIZED"


def test_me_sends_the_token_and_reads_the_member() -> None:
    seen: list = []
    me = Glyphh(SERVER, token="tok-1", transport=answering(200, ME, seen)).me()
    assert me == Me(
        id=ME["id"],
        email="ada@acme.test",
        first_name="Ada",
        last_name=None,
        image_url=None,
        role="org_admin",
        org=MeOrg(id=ME["org"]["id"], name="Acme", plan="Free"),
    )
    assert seen[0].headers["authorization"] == "Bearer tok-1"


def test_the_token_comes_from_glyphh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list = []
    monkeypatch.setenv("GLYPHH_TOKEN", "tok-env")
    Glyphh(SERVER, transport=answering(200, [HOST], seen)).list_hosts()
    assert seen[0].headers["authorization"] == "Bearer tok-env"


def test_hosts_are_listed_and_disconnected() -> None:
    hosts = Glyphh(SERVER, token="t", transport=answering(200, [HOST])).list_hosts()
    assert hosts == [
        Host(id=HOST["id"], name="Claude Code", connected_at=datetime.fromisoformat("2026-10-11T12:00:00+00:00"))
    ]
    seen: list = []
    assert Glyphh(SERVER, token="t", transport=answering(204, None, seen)).disconnect_host(HOST["id"]) is None
    assert (seen[0].method, seen[0].url.path) == ("DELETE", f"/v1/me/hosts/{HOST['id']}")


async def test_async_calls_match_sync() -> None:
    glyphh = AsyncGlyphh(SERVER, token="t", transport=answering(200, ME))
    assert (await glyphh.me()).email == "ada@acme.test"
    assert await AsyncGlyphh(SERVER, token="t", transport=answering(200, [HOST])).list_hosts()
    assert await AsyncGlyphh(SERVER, token="t", transport=answering(204)).disconnect_host(HOST["id"]) is None
    with pytest.raises(GlyphhError) as e:
        await AsyncGlyphh(
            SERVER, token="t", transport=answering(404, {"error": {"code": "E_NOT_FOUND"}})
        ).disconnect_host(HOST["id"])
    assert e.value.code == "E_NOT_FOUND"


def test_a_refusal_that_is_not_the_servers_shape_keeps_its_body() -> None:
    with pytest.raises(GlyphhError) as e:
        Glyphh(SERVER, token="t", transport=answering(502, {"error": "gateway"})).me()
    assert (e.value.status, e.value.code, e.value.trace_id, e.value.body) == (502, None, None, {"error": "gateway"})
    assert str(e.value) == "Glyphh request failed with status 502"
