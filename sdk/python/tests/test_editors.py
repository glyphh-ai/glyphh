import json

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh

SERVER = "http://localhost:8080"
S = "7f0c7b1e-0000-4000-8000-0000000000a1"
P = "7f0c7b1e-0000-4000-8000-0000000000a2"
M = "7f0c7b1e-0000-4000-8000-0000000000a3"
FLOW = {"nodes": [{"id": "t", "kind": "trigger", "label": "8am"}], "edges": []}
SCHEDULE = {"power_id": P, "machine_id": M, "name": "Weekdays", "cron": "0 8 * * 1-5"}

# api, name, args, kwargs, method, path, query
CALLS = [
    (
        "super_powers",
        "list",
        (),
        {"status": "working", "machine": M},
        "GET",
        "/v1/super-powers",
        f"q=&status=working&machine={M}&page=1&size=12",
    ),
    ("super_powers", "list", (), {}, "GET", "/v1/super-powers", "q=&status=all&page=1&size=12"),
    ("super_powers", "create", ("Scout", "Find leads."), {}, "POST", "/v1/super-powers", ""),
    ("super_powers", "glyphh", (), {}, "GET", "/v1/super-powers/glyphh", ""),
    ("super_powers", "get", (S,), {}, "GET", f"/v1/super-powers/{S}", ""),
    ("super_powers", "change", (S,), {"personality": 5}, "PATCH", f"/v1/super-powers/{S}", ""),
    ("super_powers", "delete", (S,), {}, "DELETE", f"/v1/super-powers/{S}", ""),
    ("super_powers", "grant", (S,), {"power_id": P, "access": "write"}, "PUT", f"/v1/super-powers/{S}/grants", ""),
    ("super_powers", "set_loop", (S, "codex"), {}, "PUT", f"/v1/super-powers/{S}/loop", ""),
    ("super_powers", "set_loop", (S, "glyphh", S), {}, "PUT", f"/v1/super-powers/{S}/loop", ""),
    ("custom", "list", (), {"kind": "skill"}, "GET", "/v1/powers/custom", "kind=skill&q=&page=1&size=25"),
    ("custom", "list", (), {}, "GET", "/v1/powers/custom", "q=&page=1&size=25"),
    ("custom", "create", ("task", "Briefing"), {}, "POST", "/v1/powers/custom", ""),
    ("custom", "get", (P,), {}, "GET", f"/v1/powers/custom/{P}", ""),
    ("custom", "change", (P,), {"description": "x"}, "PATCH", f"/v1/powers/custom/{P}", ""),
    ("custom", "delete", (P,), {}, "DELETE", f"/v1/powers/custom/{P}", ""),
    ("custom", "read_file", (P, "SKILL.md"), {}, "GET", f"/v1/powers/custom/{P}/file", "path=SKILL.md"),
    ("custom", "write_file", (P, "SKILL.md", "# x"), {}, "PUT", f"/v1/powers/custom/{P}/file", ""),
    ("custom", "delete_file", (P, "a.md"), {}, "DELETE", f"/v1/powers/custom/{P}/file", "path=a.md"),
    ("custom", "save_flow", (P, FLOW), {}, "PUT", f"/v1/powers/custom/{P}/flow", ""),
    ("custom", "slots", (P,), {}, "GET", f"/v1/powers/custom/{P}/slots", ""),
    ("custom", "set_slots", (P, [{"name": "main"}]), {}, "PUT", f"/v1/powers/custom/{P}/slots", ""),
    ("schedules", "list", (), {"target": P}, "GET", "/v1/schedules", f"target={P}"),
    ("schedules", "list", (), {}, "GET", "/v1/schedules", ""),
    ("schedules", "add", (), SCHEDULE, "POST", "/v1/schedules", ""),
    ("schedules", "change", (S,), SCHEDULE, "PUT", f"/v1/schedules/{S}", ""),
    ("schedules", "delete", (S,), {}, "DELETE", f"/v1/schedules/{S}", ""),
]


def answering(seen: list) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    return httpx.MockTransport(handle)


@pytest.mark.parametrize(("api", "name", "args", "kwargs", "method", "path", "query"), CALLS)
def test_each_editor_call_reaches_its_route(api, name, args, kwargs, method, path, query) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    getattr(getattr(Glyphh(SERVER, token="t", transport=answering(seen)), api), name)(*args, **kwargs)
    assert (seen[0].method, seen[0].url.path, seen[0].url.query.decode()) == (method, path, query)


@pytest.mark.parametrize(("api", "name", "args", "kwargs", "method", "path", "query"), CALLS)
async def test_async_editor_calls_match(api, name, args, kwargs, method, path, query) -> None:  # type: ignore[no-untyped-def]
    seen: list = []
    await getattr(getattr(AsyncGlyphh(SERVER, token="t", transport=answering(seen)), api), name)(*args, **kwargs)
    assert (seen[0].method, seen[0].url.path) == (method, path)


def test_bodies_are_sent_as_the_server_reads_them() -> None:
    seen: list = []
    g = Glyphh(SERVER, token="t", transport=answering(seen))
    g.super_powers.grant(S, machine_id=M)
    g.custom.save_flow(P, FLOW)
    assert json.loads(seen[0].content)["machine_id"] == M
    assert json.loads(seen[1].content)["nodes"][0]["kind"] == "trigger"
    with pytest.raises(AttributeError):
        g.custom.nothing  # noqa: B018
