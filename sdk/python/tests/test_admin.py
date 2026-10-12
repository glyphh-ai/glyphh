from datetime import UTC, datetime
from functools import reduce

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh

SERVER = "http://localhost:8080"
OG = "7f0c7b1e-0000-4000-8000-0000000000a1"
P = "7f0c7b1e-0000-4000-8000-0000000000a2"
M = "7f0c7b1e-0000-4000-8000-0000000000a3"
C = "7f0c7b1e-0000-4000-8000-0000000000a4"
AT = datetime(2026, 10, 1, tzinfo=UTC)
ORG = f"/v1/admin/orgs/{OG}"
SETTINGS = {"call_cents": 2, "seconds_per_charge": 30, "top_up_min_cents": 500, "top_up_max_cents": 1000}

# api, name, args, kwargs, method, path, query
CALLS = [
    ("admin", "orgs", (), {}, "GET", "/v1/admin/orgs", "q=&page=1&size=25"),
    (
        "admin",
        "orgs",
        (),
        {"family": "Solo", "state": "active", "kind": "team"},
        "GET",
        "/v1/admin/orgs",
        "q=&family=Solo&state=active&kind=team&page=1&size=25",
    ),
    ("admin", "org", (OG,), {}, "GET", ORG, ""),
    ("admin", "members", (OG,), {"q": "a"}, "GET", f"{ORG}/members", "q=a&page=1&size=25"),
    ("admin", "machines", (OG,), {}, "GET", f"{ORG}/machines", "page=1&size=25"),
    ("admin", "powers", (OG,), {"kind": "skill"}, "GET", f"{ORG}/powers", "kind=skill&page=1&size=25"),
    ("admin", "powers", (OG,), {}, "GET", f"{ORG}/powers", "page=1&size=25"),
    ("admin", "super_powers", (OG,), {}, "GET", f"{ORG}/super-powers", "page=1&size=25"),
    ("admin", "ledger", (OG,), {"page": 2}, "GET", f"{ORG}/ledger", "page=2&size=25"),
    ("admin", "gift", (OG, 500, "hi"), {}, "POST", f"{ORG}/gift", ""),
    ("admin", "comp", (OG, P), {}, "POST", f"{ORG}/comp", ""),
    ("admin", "end_comp", (OG,), {}, "DELETE", f"{ORG}/comp", ""),
    ("admin", "move", (OG, P), {}, "POST", f"{ORG}/move", ""),
    ("admin", "disable", (OG, "why"), {}, "POST", f"{ORG}/disable", ""),
    ("admin", "enable", (OG,), {}, "POST", f"{ORG}/enable", ""),
    ("admin", "plans", (), {}, "GET", "/v1/admin/plans", ""),
    (
        "admin",
        "next_version",
        ("Solo",),
        {"price_cents": 0, "monthly_credit_cents": 0},
        "POST",
        "/v1/admin/plans/Solo",
        "",
    ),
    ("admin", "move_orgs", (P,), {}, "POST", f"/v1/admin/plans/{P}/move", ""),
    ("admin", "billing_settings", (), {}, "GET", "/v1/admin/billing-settings", ""),
    ("admin", "set_billing_settings", (), SETTINGS, "POST", "/v1/admin/billing-settings", ""),
    ("admin.catalog", "providers", (), {"state": "off"}, "GET", "/v1/admin/providers", "q=&state=off"),
    ("admin.catalog", "providers", (), {}, "GET", "/v1/admin/providers", "q="),
    ("admin.catalog", "add_provider", (), {"slug": "a", "name": "A"}, "POST", "/v1/admin/providers", ""),
    ("admin.catalog", "change_provider", (P,), {"active": False}, "PATCH", f"/v1/admin/providers/{P}", ""),
    ("admin.catalog", "remove_provider", (P,), {}, "DELETE", f"/v1/admin/providers/{P}", ""),
    ("admin.catalog", "import_models", (P, "sk"), {}, "POST", f"/v1/admin/providers/{P}/import", ""),
    ("admin.catalog", "set_logo", (P, b"\x89PNG"), {"dark": True}, "PUT", f"/v1/admin/providers/{P}/logo", "dark=true"),
    ("admin.catalog", "set_logo", (P, b"\x89PNG"), {}, "PUT", f"/v1/admin/providers/{P}/logo", "dark=false"),
    ("admin.catalog", "models", (), {}, "GET", "/v1/admin/catalog-models", "q=&no_description=false&page=1&size=25"),
    (
        "admin.catalog",
        "models",
        (),
        {"provider": "acme", "state": "on", "type": "chat", "no_description": True},
        "GET",
        "/v1/admin/catalog-models",
        "provider=acme&q=&state=on&type=chat&no_description=true&page=1&size=25",
    ),
    (
        "admin.catalog",
        "add_model",
        (),
        {"provider_id": P, "model": "m", "name": "M"},
        "POST",
        "/v1/admin/catalog-models",
        "",
    ),
    ("admin.catalog", "change_model", (M,), {"active": True}, "PATCH", f"/v1/admin/catalog-models/{M}", ""),
    ("admin.catalog", "remove_model", (M,), {}, "DELETE", f"/v1/admin/catalog-models/{M}", ""),
    (
        "admin.market",
        "listings",
        (),
        {"state": "featured"},
        "GET",
        "/v1/admin/listings",
        "q=&state=featured&page=1&size=25",
    ),
    ("admin.market", "listings", (), {}, "GET", "/v1/admin/listings", "q=&page=1&size=25"),
    ("admin.market", "set_featured", ([M],), {}, "PUT", "/v1/admin/featured", ""),
    ("admin.market", "report", (M, {"ok": True}), {}, "PUT", f"/v1/admin/reviews/{M}/report", ""),
    ("admin.market", "categories", (), {}, "GET", "/v1/admin/categories", ""),
    ("admin.market", "add_category", ("A",), {}, "POST", "/v1/admin/categories", ""),
    ("admin.market", "rename_category", (C, "B"), {}, "PATCH", f"/v1/admin/categories/{C}", ""),
    ("admin.market", "delete_category", (C,), {}, "DELETE", f"/v1/admin/categories/{C}", ""),
    ("admin.market", "order_categories", ([C],), {}, "PUT", "/v1/admin/categories", ""),
    ("admin.market", "audit", (), {}, "GET", "/v1/admin/audit", "page=1&size=25"),
    (
        "admin.market",
        "audit",
        (),
        {"since": AT, "until": AT, "who": OG, "type": "plans", "target": "org", "org": OG},
        "GET",
        "/v1/admin/audit",
        f"page=1&size=25&since=2026-10-01T00%3A00%3A00%2B00%3A00&until=2026-10-01T00%3A00%3A00%2B00%3A00&who={OG}"
        f"&type=plans&target=org&org={OG}",
    ),
    ("admin.market", "export_audit", (), {"type": "models"}, "GET", "/v1/admin/audit.csv", "type=models"),
]


def answering(seen: list) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    return httpx.MockTransport(handle)


def _api(client, api):  # type: ignore[no-untyped-def]
    return reduce(getattr, api.split("."), client)


@pytest.mark.parametrize(("api", "name", "args", "kwargs", "method", "path", "query"), CALLS)
def test_each_call_reaches_its_route(api, name, args, kwargs, method, path, query) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    getattr(_api(Glyphh(SERVER, token="t", transport=answering(seen)), api), name)(*args, **kwargs)
    assert (seen[0].method, seen[0].url.path, seen[0].url.query.decode()) == (method, path, query)


@pytest.mark.parametrize(("api", "name", "args", "kwargs", "method", "path", "query"), CALLS)
async def test_async_calls_match(api, name, args, kwargs, method, path, query) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    await getattr(_api(AsyncGlyphh(SERVER, token="t", transport=answering(seen)), api), name)(*args, **kwargs)
    assert (seen[0].method, seen[0].url.path) == (method, path)
