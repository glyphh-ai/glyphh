import json
from datetime import UTC, datetime

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh

SERVER = "http://localhost:8080"
T = "7f0c7b1e-0000-4000-8000-0000000000c1"
U = "7f0c7b1e-0000-4000-8000-0000000000c2"
K = "7f0c7b1e-0000-4000-8000-0000000000c3"
AT = datetime(2026, 10, 1, tzinfo=UTC)

# api, name, args, kwargs, method, path, query
CALLS = [
    ("org_admin", "people", (), {}, "GET", "/v1/org/people", "q=&page=1&size=25"),
    (
        "org_admin",
        "people",
        (),
        {"q": "bo", "role": "user", "team": [T, "none"]},
        "GET",
        "/v1/org/people",
        f"q=bo&role=user&team={T}&team=none&page=1&size=25",
    ),
    ("org_admin", "invite_many", (["a@x.test"],), {"team_ids": [T]}, "POST", "/v1/org/invites/many", ""),
    ("org_admin", "teams", (), {}, "GET", "/v1/org/teams", ""),
    ("org_admin", "team", (T,), {}, "GET", f"/v1/org/teams/{T}", ""),
    ("org_admin", "create_team", ("Design",), {}, "POST", "/v1/org/teams", ""),
    ("org_admin", "change_team", (T,), {"limit_models": True}, "PATCH", f"/v1/org/teams/{T}", ""),
    ("org_admin", "delete_team", (T,), {}, "DELETE", f"/v1/org/teams/{T}", ""),
    ("org_admin", "add_to_team", (T, [U]), {}, "POST", f"/v1/org/teams/{T}/members", ""),
    ("org_admin", "remove_from_team", (T, U), {}, "DELETE", f"/v1/org/teams/{T}/members/{U}", ""),
    ("org_admin", "member_teams", (U,), {}, "GET", f"/v1/org/members/{U}/teams", ""),
    ("org_admin", "set_member_teams", (U, [T]), {}, "PUT", f"/v1/org/members/{U}/teams", ""),
    ("org_admin", "limits", ("models",), {}, "GET", "/v1/org/limits/models", "q=&page=1&size=25"),
    (
        "org_admin",
        "limits",
        ("connections",),
        {"team": T, "q": "g"},
        "GET",
        "/v1/org/limits/connections",
        f"team={T}&q=g&page=1&size=25",
    ),
    ("org_admin", "limit_impact", ("models",), {"team": T}, "GET", "/v1/org/limits/models/impact", f"team={T}"),
    ("org_admin", "set_limit", ("models", True), {}, "PUT", "/v1/org/limits/models/switch", ""),
    (
        "org_admin",
        "add_limit_entries",
        ("connections", ["gmail"]),
        {},
        "POST",
        "/v1/org/limits/connections/entries",
        "",
    ),
    (
        "org_admin",
        "remove_limit_entries",
        ("connections", ["gmail"]),
        {"team": T},
        "POST",
        "/v1/org/limits/connections/entries/remove",
        f"team={T}",
    ),
    ("org_admin", "audit_log", (), {}, "GET", "/v1/org/audit", "page=1&size=25"),
    (
        "org_admin",
        "audit_log",
        (),
        {"since": AT, "who": U, "type": "glyphh", "target": "team", "page": 2},
        "GET",
        "/v1/org/audit",
        f"page=2&size=25&since=2026-10-01T00%3A00%3A00%2B00%3A00&who={U}&type=glyphh&target=team",
    ),
    ("org_admin", "export_audit_log", (), {"type": "keys"}, "GET", "/v1/org/audit.csv", "type=keys"),
    ("api_keys", "mine", (), {}, "GET", "/v1/me/api-keys", "page=1&size=25"),
    ("api_keys", "make", ("Nightly CI",), {"expires": "never"}, "POST", "/v1/me/api-keys", ""),
    ("api_keys", "revoke", (K,), {}, "POST", f"/v1/api-keys/{K}/revoke", ""),
    ("api_keys", "org", (), {"owner": U}, "GET", "/v1/org/api-keys", f"owner={U}&page=1&size=25"),
    ("api_keys", "makers", (), {"q": "bo"}, "GET", "/v1/org/api-keys/makers", "q=bo"),
    ("api_keys", "member_keys", (), {}, "GET", "/v1/org/api-keys/member-keys", ""),
    ("api_keys", "set_member_keys", (False,), {}, "PUT", "/v1/org/api-keys/member-keys", ""),
]


def answering(seen: list, body: object = None, status: int = 200) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204) if body is None else httpx.Response(status, content=json.dumps(body).encode())

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


def test_a_new_key_comes_back_once_with_its_secret() -> None:
    seen: list = []
    key = {"id": K, "name": "CI", "prefix": "gk_live_ab12", "owner": "Bo", "owner_id": U, "status": "active"}
    key |= {"created_at": AT.isoformat(), "last_used_at": None, "expires_at": None}
    made = {"key": key, "secret": "gk_live_ab12xyz"}
    answer = Glyphh(SERVER, token="t", transport=answering(seen, made, 201)).api_keys.make("CI")
    assert answer["secret"] == "gk_live_ab12xyz"
    assert json.loads(seen[0].content) == {"name": "CI", "expires": "90d"}
