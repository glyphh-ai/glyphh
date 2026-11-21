"""The connector's grants from the account: listed, revoked one by one, each person's own."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.connector import granted
from tests.db.helpers import person


async def test_grants_are_listed_and_revoked_from_the_account(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada, eve = await person(engine), await person(engine)
    grant_id, auth = await granted(engine, ada)
    await granted(engine, eve)
    (listed,) = (await client.get("/v1/connector/grants", headers=ada.headers)).json()
    assert (listed["id"], listed["client"], listed["scope"], listed["current"]) == (
        str(grant_id),
        "Claude",
        "account",
        False,
    )
    assert listed["last_used_at"] is None
    assert (await client.delete(f"/v1/connector/grants/{grant_id}", headers=eve.headers)).status_code == 404
    assert (
        await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, headers=auth)
    ).status_code == 200
    (used,) = (await client.get("/v1/connector/grants", headers=ada.headers)).json()
    assert used["last_used_at"] is not None
    assert (await client.delete(f"/v1/connector/grants/{grant_id}", headers=ada.headers)).status_code == 204
    assert (await client.get("/v1/connector/grants", headers=ada.headers)).json() == []
    assert (await client.post("/mcp", json={}, headers=auth)).status_code == 401
    assert (await client.delete(f"/v1/connector/grants/{grant_id}", headers=ada.headers)).status_code == 404
    assert (await client.get("/v1/connector/grants")).status_code == 401
