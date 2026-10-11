import os

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh, GlyphhError, Health

SERVER: str = os.environ.get("GLYPHH_URL") or "http://localhost:8080"


def refusing(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, json={"detail": "down"})


def not_json(request: httpx.Request) -> httpx.Response:
    return httpx.Response(502, text="bad gateway")


def unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def test_health_answers_from_the_real_server() -> None:
    health = Glyphh(SERVER).health()
    assert isinstance(health, Health)
    assert (health.status, health.database) == ("ok", True)


async def test_async_health_answers_from_the_real_server() -> None:
    assert (await AsyncGlyphh(SERVER).health()).database is True


def test_a_refusal_is_a_glyphh_error_with_status_and_body() -> None:
    with pytest.raises(GlyphhError) as e:
        Glyphh(SERVER, transport=httpx.MockTransport(refusing)).health()
    assert (e.value.status, e.value.body) == (503, {"detail": "down"})


def test_a_body_that_is_not_json_is_kept_as_text() -> None:
    with pytest.raises(GlyphhError) as e:
        Glyphh(SERVER, transport=httpx.MockTransport(not_json)).health()
    assert (e.value.status, e.value.body) == (502, "bad gateway")


def test_an_unreachable_server_is_status_0() -> None:
    with pytest.raises(GlyphhError) as e:
        Glyphh(SERVER, transport=httpx.MockTransport(unreachable)).health()
    assert e.value.status == 0


async def test_async_errors_match_sync() -> None:
    with pytest.raises(GlyphhError) as refused:
        await AsyncGlyphh(SERVER, transport=httpx.MockTransport(refusing)).health()
    assert refused.value.status == 503
    with pytest.raises(GlyphhError) as gone:
        await AsyncGlyphh(SERVER, transport=httpx.MockTransport(unreachable)).health()
    assert gone.value.status == 0


def test_the_server_comes_from_glyphh_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLYPHH_URL", SERVER)
    assert Glyphh().health().database is True


def test_a_server_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLYPHH_URL", raising=False)
    with pytest.raises(ValueError, match="needs a server"):
        Glyphh()
