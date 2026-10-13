from datetime import UTC, date, datetime

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh

SERVER = "http://localhost:8080"
S = "7f0c7b1e-0000-4000-8000-0000000000d1"
U = "7f0c7b1e-0000-4000-8000-0000000000d2"
L = "7f0c7b1e-0000-4000-8000-0000000000d3"
AT = datetime(2026, 10, 1, tzinfo=UTC)

# api, name, args, kwargs, method, path, query
CALLS = [
    ("usage", "page", (), {}, "GET", "/v1/usage", "scope=me"),
    (
        "usage",
        "page",
        (),
        {"scope": "org", "since": date(2026, 10, 1), "users": [U], "super_power": S, "service": "gmail"},
        "GET",
        "/v1/usage",
        f"scope=org&since=2026-10-01&users={U}&super_power={S}&service=gmail",
    ),
    ("usage", "by", ("models",), {"machine": None}, "GET", "/v1/usage/by/models", "page=1&size=25&scope=me"),
    ("usage", "runs", (), {"super_power": S}, "GET", "/v1/usage/runs", f"page=1&size=25&scope=me&super_power={S}"),
    ("usage", "periods", (), {}, "GET", "/v1/usage/periods", ""),
    ("usage", "calls", (), {}, "GET", "/v1/usage/calls", "size=50&scope=me"),
    (
        "usage",
        "calls",
        (),
        {"after": "c", "since": AT, "status": "error", "error": True, "teams": [U], "run": S},
        "GET",
        "/v1/usage/calls",
        f"after=c&size=50&scope=me&since=2026-10-01T00%3A00%3A00%2B00%3A00&teams={U}&run={S}&status=error&error=true",
    ),
    ("usage", "call", (S,), {"scope": "org"}, "GET", f"/v1/usage/calls/{S}", "scope=org"),
    ("usage", "export_calls", (), {"tool": "x"}, "GET", "/v1/usage/calls.csv", "scope=me&tool=x"),
    ("usage", "uses", (), {"kind": "model_call"}, "GET", "/v1/usage/uses", "size=50&scope=me&kind=model_call"),
    ("usage", "use", (S,), {}, "GET", f"/v1/usage/uses/{S}", "scope=me"),
    ("usage", "export_uses", (), {"status": "ok"}, "GET", "/v1/usage/uses.csv", "scope=me&status=ok"),
    ("usage", "listing_stats", (L,), {"days": 7}, "GET", f"/v1/listings/{L}/stats", "days=7"),
    ("hosting", "save_account", ("FlyV1 fm2_x",), {"account": "my-org"}, "PUT", "/v1/hosts/fly/account", ""),
    ("hosting", "account", (), {}, "GET", "/v1/hosts/fly/account", ""),
    ("hosting", "remove_account", (), {}, "DELETE", "/v1/hosts/fly/account", ""),
    ("hosting", "deploy", ("attic",), {"region": "ams"}, "POST", "/v1/hosted-machines", ""),
    ("hosting", "list", (), {}, "GET", "/v1/hosted-machines", ""),
    ("hosting", "get", (S,), {}, "GET", f"/v1/hosted-machines/{S}", ""),
    ("hosting", "start", (S,), {}, "POST", f"/v1/hosted-machines/{S}/start", ""),
    (
        "hosting",
        "update",
        (S,),
        {"image": "rrotor:1.2"},
        "POST",
        f"/v1/hosted-machines/{S}/update",
        "",
    ),
    ("hosting", "destroy", (S,), {}, "DELETE", f"/v1/hosted-machines/{S}", ""),
]


def answering(seen: list) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

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


def test_a_csv_comes_back_as_text() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="started_at,user\n", headers={"content-type": "text/csv"})

    assert Glyphh(SERVER, token="t", transport=httpx.MockTransport(handle)).usage.export_calls() == "started_at,user\n"
