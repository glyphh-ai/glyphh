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
    "signed_in_with": "google",
    "role": "org_admin",
    "org": {
        "id": "7f0c7b1e-0000-4000-8000-000000000002",
        "name": "Acme",
        "plan": "Free",
        "personal": False,
        "people": 3,
        "role": "org_admin",
    },
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
        signed_in_with="google",
        role="org_admin",
        org=MeOrg(id=ME["org"]["id"], name="Acme", plan="Free", personal=False, role="org_admin", people=3),
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


def test_my_orgs_and_answering_an_invite_sync_and_async() -> None:
    orgs = [{**ME["org"], "name": "Personal", "personal": True}, ME["org"]]
    listed = Glyphh(SERVER, token="t", transport=answering(200, orgs)).list_my_orgs()
    assert [(o.name, o.personal) for o in listed] == [("Personal", True), ("Acme", False)]
    seen: list = []
    assert Glyphh(SERVER, token="t", transport=answering(200, {"org": "Acme"}, seen)).accept_invite("I1") == "Acme"
    assert (seen[0].method, seen[0].url.path, seen[0].content) == ("POST", "/v1/invites/accept", b'{"invite":"I1"}')
    Glyphh(SERVER, token="t", transport=answering(204)).decline_invite("I2")


async def test_my_orgs_and_answering_an_invite_async() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/me/orgs":
            return httpx.Response(200, json=[ME["org"]])
        if request.url.path == "/v1/invites/accept":
            return httpx.Response(200, json={"org": "Acme"})
        return httpx.Response(204)

    sdk = AsyncGlyphh(SERVER, token="t", transport=httpx.MockTransport(handle))
    assert [o.name for o in await sdk.list_my_orgs()] == ["Acme"]
    assert await sdk.accept_invite("I1") == "Acme"
    assert await sdk.decline_invite("I2") is None


def test_i_change_my_name_and_sign_out_everywhere() -> None:
    seen: list = []
    me = Glyphh(SERVER, token="t", transport=answering(200, {**ME, "first_name": "Grace"}, seen)).change_me(
        first_name="Grace"
    )
    assert me.first_name == "Grace"
    assert (seen[0].method, seen[0].url.path, seen[0].content) == ("PATCH", "/v1/me", b'{"first_name":"Grace"}')
    out: list = []
    assert Glyphh(SERVER, token="t", transport=answering(204, None, out)).sign_out_everywhere() is None
    assert (out[0].method, out[0].url.path) == ("POST", "/v1/session/sign-out-everywhere")


async def test_async_i_change_my_name_and_sign_out_everywhere() -> None:
    me = await AsyncGlyphh(SERVER, token="t", transport=answering(200, ME)).change_me(last_name="")
    assert me.signed_in_with == "google"
    assert await AsyncGlyphh(SERVER, token="t", transport=answering(204)).sign_out_everywhere() is None
