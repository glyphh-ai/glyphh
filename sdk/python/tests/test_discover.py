import json

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh

SERVER = "http://localhost:8080"
L = "7f0c7b1e-0000-4000-8000-0000000000b1"
V = "7f0c7b1e-0000-4000-8000-0000000000b2"

# api, name, args, kwargs, method, path, query
CALLS = [
    ("listings", "mine", (), {}, "GET", "/v1/listings", ""),
    ("listings", "create", (), {"power_id": L}, "POST", "/v1/listings", ""),
    ("listings", "get", (L,), {}, "GET", f"/v1/listings/{L}", ""),
    ("listings", "change", (L,), {"summary": "s"}, "PATCH", f"/v1/listings/{L}", ""),
    ("listings", "change_version", (L,), {"version": "1.1.0"}, "PATCH", f"/v1/listings/{L}/version", ""),
    ("listings", "set_icon", (L, b"\x89PNG"), {"name": "icon.png"}, "PUT", f"/v1/listings/{L}/icon", ""),
    (
        "listings",
        "add_screenshot",
        (L, b"\xff\xd8"),
        {"content_type": "image/jpeg"},
        "POST",
        f"/v1/listings/{L}/screenshots",
        "",
    ),
    ("listings", "order_screenshots", (L, [V]), {}, "PUT", f"/v1/listings/{L}/screenshots", ""),
    ("listings", "remove_screenshot", (L, V), {}, "DELETE", f"/v1/listings/{L}/screenshots/{V}", ""),
    ("listings", "submit", (L,), {}, "POST", f"/v1/listings/{L}/submit", ""),
    ("listings", "withdraw", (L,), {}, "POST", f"/v1/listings/{L}/withdraw", ""),
    ("listings", "unpublish", (L,), {}, "POST", f"/v1/listings/{L}/unpublish", ""),
    ("listings", "comments", (L,), {}, "GET", f"/v1/listings/{L}/comments", ""),
    ("listings", "comment", (L, "hi"), {}, "POST", f"/v1/listings/{L}/comments", ""),
    ("listings", "queue", (), {"step": "glyphh"}, "GET", "/v1/reviews", "step=glyphh"),
    ("listings", "decide", (V, "approved"), {}, "POST", f"/v1/reviews/{V}", ""),
    ("marketplace", "home", (), {"kind": "custom"}, "GET", "/v1/marketplace/home", "kind=custom"),
    ("marketplace", "home", (), {}, "GET", "/v1/marketplace/home", ""),
    (
        "marketplace",
        "browse",
        (),
        {"kind": "super_power", "type": "skill", "category": "sales", "q": "x"},
        "GET",
        "/v1/marketplace",
        "kind=super_power&type=skill&category=sales&q=x&page=1&size=24",
    ),
    ("marketplace", "browse", (), {}, "GET", "/v1/marketplace", "q=&page=1&size=24"),
    ("marketplace", "get", (L,), {}, "GET", f"/v1/marketplace/{L}", ""),
    ("marketplace", "add", (L,), {}, "POST", f"/v1/marketplace/{L}/add", ""),
    ("marketplace", "update", (L,), {}, "POST", f"/v1/powers/custom/{L}/update", ""),
    ("marketplace", "update_super_power", (L,), {}, "POST", f"/v1/super-powers/{L}/update", ""),
]


def answering(seen: list, body: object = None) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204) if body is None else httpx.Response(200, content=json.dumps(body).encode())

    return httpx.MockTransport(handle)


@pytest.mark.parametrize(("api", "name", "args", "kwargs", "method", "path", "query"), CALLS)
def test_each_call_reaches_its_route(api, name, args, kwargs, method, path, query) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    getattr(getattr(Glyphh(SERVER, token="t", transport=answering(seen)), api), name)(*args, **kwargs)
    assert (seen[0].method, seen[0].url.path, seen[0].url.query.decode()) == (method, path, query)


@pytest.mark.parametrize(("api", "name", "args", "kwargs", "method", "path", "query"), CALLS)
async def test_async_calls_match(api, name, args, kwargs, method, path, query) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    await getattr(getattr(AsyncGlyphh(SERVER, token="t", transport=answering(seen)), api), name)(*args, **kwargs)
    assert (seen[0].method, seen[0].url.path) == (method, path)


def test_a_picture_is_sent_as_its_own_bytes() -> None:
    seen: list = []
    answer = Glyphh(SERVER, token="t", transport=answering(seen, {"id": L})).listings.set_icon(
        L, b"\x89PNG", name="i.png"
    )
    assert answer == {"id": L}
    assert (seen[0].content, seen[0].headers["content-type"], seen[0].headers["x-file-name"]) == (
        b"\x89PNG",
        "image/png",
        "i.png",
    )
