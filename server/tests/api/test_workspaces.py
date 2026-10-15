"""Workspace names, for the plan's limit."""

import httpx
from sqlalchemy import delete, insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Org, Plan, PlanVersion
from glyphh_server.ops.plans import newest_version
from tests.db.helpers import person


async def test_workspaces_are_made_listed_renamed_and_deleted(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    made = await client.post("/v1/workspaces", json={"name": " Inbox zero "}, headers=ada.headers)
    assert made.status_code == 201 and made.json()["name"] == "Inbox zero"
    await client.post("/v1/workspaces", json={"name": "Code"}, headers=ada.headers)
    renamed = await client.patch("/v1/workspaces/Inbox zero", json={"name": "Mail"}, headers=ada.headers)
    assert renamed.status_code == 200 and renamed.json()["name"] == "Mail"
    names = [w["name"] for w in (await client.get("/v1/workspaces", headers=ada.headers)).json()]
    assert names == ["Mail", "Code"]
    assert (await client.delete("/v1/workspaces/Mail", headers=ada.headers)).status_code == 204
    assert [w["name"] for w in (await client.get("/v1/workspaces", headers=ada.headers)).json()] == ["Code"]


async def test_names_are_unique_and_unknown_ones_are_not_found(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    for name in ("A", "B"):
        await client.post("/v1/workspaces", json={"name": name}, headers=ada.headers)
    dup = await client.post("/v1/workspaces", json={"name": "A"}, headers=ada.headers)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "E_CONFLICT"
    clash = await client.patch("/v1/workspaces/A", json={"name": "B"}, headers=ada.headers)
    assert clash.status_code == 409
    for res in (
        await client.patch("/v1/workspaces/Z", json={"name": "Y"}, headers=ada.headers),
        await client.delete("/v1/workspaces/Z", headers=ada.headers),
    ):
        assert res.status_code == 404 and res.json()["error"]["code"] == "E_NOT_FOUND"
    assert (await client.post("/v1/workspaces", json={"name": "   "}, headers=ada.headers)).status_code == 422


async def test_a_workspace_past_the_plan_is_refused_naming_the_plan_that_lifts_it(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    for name in ("One", "Two"):
        assert (await client.post("/v1/workspaces", json={"name": name}, headers=ada.headers)).status_code == 201
    res = await client.post("/v1/workspaces", json={"name": "Three"}, headers=ada.headers)
    assert res.status_code == 403
    err = res.json()["error"]
    assert (err["code"], err["limit"], err["used"], err["max"], err["plan"]) == ("E_LIMIT", "workspaces", 2, 2, "Pro")
    assert "Pro allows more" in err["message"]


async def test_workspaces_are_each_persons_own(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada, bob = await person(engine), await person(engine)
    await client.post("/v1/workspaces", json={"name": "Mine"}, headers=ada.headers)
    assert (await client.get("/v1/workspaces", headers=bob.headers)).json() == []
    assert (await client.delete("/v1/workspaces/Mine", headers=bob.headers)).status_code == 404


async def test_a_plan_without_the_workspaces_mod_allows_no_workspace(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    async with engine.begin() as conn:
        plan_id = (await conn.execute(insert(Plan).values(name="Drips only", sort=8).returning(Plan.id))).scalar_one()
        limits = {"drips": {"custom_drips": 1, "fullscreen": 0}}
        values = {"plan_id": plan_id, "version": 1, "seat_price_cents": 0, "max_members": 1, "mod_limits": limits}
        version_id = (await conn.execute(insert(PlanVersion).values(values).returning(PlanVersion.id))).scalar_one()
        await conn.execute(update(Org).where(Org.id == ada.org_id).values(plan_version_id=version_id))
    try:
        res = await client.post("/v1/workspaces", json={"name": "One"}, headers=ada.headers)
        err = res.json()["error"]
        assert (res.status_code, err["limit"], err["used"], err["max"]) == (403, "workspaces", 0, 0)
    finally:
        async with engine.begin() as conn:
            free = await newest_version(conn, "Free")
            await conn.execute(update(Org).where(Org.id == ada.org_id).values(plan_version_id=free.id))
            await conn.execute(delete(PlanVersion).where(PlanVersion.plan_id == plan_id))
            await conn.execute(delete(Plan).where(Plan.id == plan_id))
