import json
from uuid import UUID

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh

SERVER = "http://localhost:8080"
P = "7f0c7b1e-0000-4000-8000-0000000000dd"
M = "7f0c7b1e-0000-4000-8000-0000000000ee"


def answering(body: object, seen: list, status: int = 200) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, content=json.dumps(body).encode(), headers={"content-type": "application/json"})

    return httpx.MockTransport(handle)


# name, args, kwargs, method, path, query, body, status
CALLS = [
    ("providers", (), {"q": "open"}, "GET", "/v1/catalog/providers", "q=open", None, 200),
    (
        "catalog_models",
        (),
        {"provider": "openai"},
        "GET",
        "/v1/catalog/models",
        "provider=openai&q=&page=1&size=25",
        None,
        200,
    ),
    ("catalog_models", (), {}, "GET", "/v1/catalog/models", "q=&page=1&size=25", None, 200),
    ("models", (), {}, "GET", "/v1/powers/models", "", None, 200),
    (
        "add_model",
        (),
        {"catalog_model_id": P, "api_key": "sk-1", "name": None},
        "POST",
        "/v1/powers/models",
        "",
        {"catalog_model_id": P, "api_key": "sk-1"},
        201,
    ),
    ("replace_key", (P, "sk-2"), {}, "PUT", f"/v1/powers/models/{P}/key", "", {"api_key": "sk-2"}, 200),
    ("check_key", (P,), {}, "POST", f"/v1/powers/models/{P}/check", "", None, 200),
    ("delete_model", (P,), {}, "DELETE", f"/v1/powers/models/{P}", "", None, 204),
    ("loops", (), {}, "GET", "/v1/powers/loops", "", None, 200),
    ("folders", (), {}, "GET", "/v1/powers/folders", "", None, 200),
    ("relay_tools", (P,), {}, "GET", f"/v1/relay/connections/{P}/tools", "mode=driven", None, 200),
    (
        "relay_tools",
        (P,),
        {"super_power_id": M, "mode": "autonomous"},
        "GET",
        f"/v1/relay/connections/{P}/tools",
        f"super_power_id={M}&mode=autonomous",
        None,
        200,
    ),
    (
        "call_tool",
        (P, "gmail-send-email"),
        {"input": {"to": "a"}, "mode": "autonomous"},
        "POST",
        "/v1/relay/call",
        "",
        {"connection_id": P, "tool": "gmail-send-email", "input": {"to": "a"}, "mode": "autonomous"},
        200,
    ),
    ("add_folder", (M, "~/Content"), {}, "POST", "/v1/powers/folders", "", {"machine_id": M, "path": "~/Content"}, 201),
    ("remove_folder", (P,), {}, "DELETE", f"/v1/powers/folders/{P}", "", None, 204),
    ("browsers", (), {}, "GET", "/v1/powers/browsers", "", None, 200),
    (
        "add_browser",
        ("Scout's", M, P),
        {},
        "POST",
        "/v1/powers/browsers",
        "",
        {"name": "Scout's", "machine_id": M, "super_power_id": P},
        201,
    ),
    ("delete_browser", (P,), {}, "DELETE", f"/v1/powers/browsers/{P}", "", None, 204),
    ("can_add", (), {}, "GET", "/v1/powers/can-add", "", None, 200),
    (
        "services",
        (),
        {"q": "gmail", "after": "c1"},
        "GET",
        "/v1/catalog/services",
        "q=gmail&after=c1&limit=25",
        None,
        200,
    ),
    ("services", (), {}, "GET", "/v1/catalog/services", "q=&limit=25", None, 200),
    ("connections", (), {}, "GET", "/v1/powers/connections", "", None, 200),
    ("connect", ("gmail",), {}, "POST", "/v1/powers/connections", "", {"service": "gmail"}, 201),
    ("reconnect", (P,), {}, "POST", f"/v1/powers/connections/{P}/link", "", None, 200),
    ("check_connection", (P,), {}, "POST", f"/v1/powers/connections/{P}/check", "", None, 200),
    ("disconnect", (P,), {}, "DELETE", f"/v1/powers/connections/{P}", "", None, 204),
    ("tools", (P,), {"q": "send"}, "GET", f"/v1/powers/connections/{P}/tools", "q=send&page=1&size=50", None, 200),
    (
        "set_tools",
        (P, [{"tool": "gmail-send-email", "permission": "allow"}]),
        {},
        "PATCH",
        f"/v1/powers/connections/{P}/tools",
        "",
        {"changes": [{"tool": "gmail-send-email", "permission": "allow"}]},
        204,
    ),
]


def _sent(r: httpx.Request) -> tuple:
    return r.method, r.url.path, r.url.query.decode(), json.loads(r.content) if r.content else None


@pytest.mark.parametrize(("name", "args", "kwargs", "method", "path", "query", "body", "status"), CALLS)
def test_each_power_call_reaches_its_route(name, args, kwargs, method, path, query, body, status) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    Glyphh(SERVER, token="t", transport=answering(None, seen, 204)).powers.__getattr__(name)(*args, **kwargs)
    sent = _sent(seen[0])
    assert sent[:3] == (method, path, query)
    assert sent[3] is None if body is None else {k: v for k, v in sent[3].items() if v is not None} == body


@pytest.mark.parametrize(("name", "args", "kwargs", "method", "path", "query", "body", "status"), CALLS)
async def test_async_power_calls_match(name, args, kwargs, method, path, query, body, status) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    await AsyncGlyphh(SERVER, token="t", transport=answering(None, seen, 204)).powers.__getattr__(name)(*args, **kwargs)
    assert _sent(seen[0])[:3] == (method, path, query)


def test_answers_are_plain_and_unknown_calls_are_refused() -> None:
    listed = [
        {"slug": "openai", "name": "OpenAI", "logo_key": None, "logo_dark_key": None, "models": 3, "blocked": None}
    ]
    assert Glyphh(SERVER, token="t", transport=answering(listed, [])).powers.providers() == listed
    with pytest.raises(AttributeError):
        Glyphh(SERVER, token="t").powers.nothing_here()  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        AsyncGlyphh(SERVER, token="t").powers.nothing_here()  # type: ignore[attr-defined]
    assert UUID(P)
