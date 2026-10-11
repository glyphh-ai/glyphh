import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.auth import tokens
from tests.db.helpers import bearer, make_client, make_org, make_user


async def test_me_answers_as_the_signed_in_member(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    auth = await bearer(engine, "me@api.test")
    res = await client.get("/v1/me", headers={"authorization": auth})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == "me@api.test" and body["role"] == "org_admin" and body["org"]["plan"] == "Enterprise"


async def test_without_a_valid_token_the_answer_is_always_unauthorized(client: httpx.AsyncClient) -> None:
    for headers in ({}, {"authorization": "Basic abc"}, {"authorization": "Bearer"}, {"authorization": "Bearer nope"}):
        res = await client.get("/v1/me", headers=headers)
        assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED"


async def test_a_member_lists_and_disconnects_their_hosts(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    user = await make_user(engine, await make_org(engine, "API Hosts Co"), "hosts@api.test")
    claude = await make_client(engine, "api-claude")
    async with engine.begin() as conn:
        issued = await tokens.issue(conn, user, claude)
        mine = await tokens.issue(conn, user)
    auth = {"authorization": f"Bearer {mine.access_token}"}
    listed = (await client.get("/v1/me/hosts", headers=auth)).json()
    assert [h["id"] for h in listed] == [str(claude)]
    assert (await client.delete(f"/v1/me/hosts/{claude}", headers=auth)).status_code == 204
    assert (await client.get("/v1/me", headers={"authorization": f"Bearer {issued.access_token}"})).status_code == 401
    gone = await client.delete(f"/v1/me/hosts/{uuid.uuid4()}", headers=auth)
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "E_NOT_FOUND"


async def test_the_openapi_spec_names_the_me_operations(client: httpx.AsyncClient) -> None:
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert paths["/v1/me"]["get"]["operationId"] == "me"
    assert paths["/v1/me/hosts"]["get"]["operationId"] == "listHosts"
    assert paths["/v1/me/hosts/{host_id}"]["delete"]["operationId"] == "disconnectHost"
