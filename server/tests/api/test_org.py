import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.auth import tokens
from tests.db.helpers import admin_of, make_user
from tests.test_health import MCP_HEADERS, _sse_result


async def _bearer(engine: AsyncEngine, user) -> dict[str, str]:
    async with engine.begin() as conn:
        return {"authorization": f"Bearer {(await tokens.issue(conn, user)).access_token}"}


async def test_an_admin_runs_the_org_through_the_api(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "API Org Co")
    auth = await _bearer(engine, boss.user_id)
    assert (await client.get("/v1/org", headers=auth)).json()["name"] == "API Org Co"
    assert (await client.patch("/v1/org", headers=auth, json={"name": "API Org"})).json()["name"] == "API Org"
    made = await client.post("/v1/org/invites", headers=auth, json={"email": "new@apiorg.test"})
    assert made.status_code == 201
    body = made.json()
    assert body["invite"]["role"] == "user" and body["link"].startswith("http://localhost:8080/auth/join?invite=")
    listed = (await client.get("/v1/org/invites", headers=auth)).json()
    assert [i["email"] for i in listed] == ["new@apiorg.test"]
    assert (await client.delete(f"/v1/org/invites/{body['invite']['id']}", headers=auth)).status_code == 204
    ada = await make_user(engine, boss.org_id, "ada@apiorg.test")
    changed = await client.patch(f"/v1/org/members/{ada}", headers=auth, json={"role": "org_admin"})
    assert changed.json()["role"] == "org_admin"
    assert len((await client.get("/v1/org/members", headers=auth)).json()) == 2
    assert (await client.delete(f"/v1/org/members/{ada}", headers=auth)).status_code == 204


async def test_the_api_refuses_bad_input_strangers_and_non_admins(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    boss = await admin_of(engine, "Refuse Co")
    member = await _bearer(engine, await make_user(engine, boss.org_id, "m@refuse.test"))
    auth = await _bearer(engine, boss.user_id)
    bad = await client.post("/v1/org/invites", headers=auth, json={"email": "not-an-email"})
    assert bad.status_code == 422 and bad.json()["error"]["problems"][0]["loc"] == ["body", "email"]
    assert (await client.patch("/v1/org", headers=member, json={"name": "x"})).json()["error"]["code"] == "E_FORBIDDEN"
    assert (await client.get("/v1/org")).status_code == 401


async def test_agents_reach_the_org_through_mcp(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "MCP Org Co")
    headers = {**MCP_HEADERS, **(await _bearer(engine, boss.user_id))}

    async def call(name: str, args: dict | None = None) -> dict:
        res = await client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args or {}}},
        )
        return _sse_result(res.text)["result"]

    assert (await call("org"))["structuredContent"]["name"] == "MCP Org Co"
    assert len((await call("members"))["structuredContent"]["result"]) == 1
    made = (await call("invite", {"email": "agent@mcporg.test"}))["structuredContent"]
    assert made["link"].startswith("http://localhost:8080/auth/join?invite=")
    open_ = (await call("invites"))["structuredContent"]["result"]
    assert [i["email"] for i in open_] == ["agent@mcporg.test"]
    done = await call("revoke_invite", {"invite_id": open_[0]["id"]})
    assert not done.get("isError")
    again = await call("revoke_invite", {"invite_id": open_[0]["id"]})
    assert again["isError"] and "E_NOT_FOUND" in again["content"][0]["text"]
