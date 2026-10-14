"""The mods catalog: free mods in every plan, the rest in the plans with all_mods, new mods reaching those as they
ship, retired mods in none."""

import httpx
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.schema import apply_schema
from glyphh_server.models import Mod
from tests.conftest import SETTINGS
from tests.db.helpers import person


async def test_the_catalog_lists_each_mod_and_the_plans_that_include_it(client: httpx.AsyncClient) -> None:
    res = await client.get("/v1/mods")
    assert res.status_code == 200
    mods = res.json()
    assert [(m["slug"], m["name"], m["free"], m["plans"]) for m in mods] == [
        ("glyphh", "Glyphh", True, ["Free", "Pro", "Team"]),
        ("glyphh-workspaces", "Glyphh Workspaces", True, ["Free", "Pro", "Team"]),
        ("glyphh-rpa", "Glyphh RPA", False, ["Pro", "Team"]),
        ("glyphh-programs", "Glyphh Programs", True, ["Free", "Pro", "Team"]),
    ]
    assert all(m["description"] for m in mods)


async def test_seeding_again_keeps_the_catalog(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        before = list(await conn.execute(select(Mod).order_by(Mod.sort)))
    await apply_schema(engine, SETTINGS)
    async with engine.connect() as conn:
        assert list(await conn.execute(select(Mod).order_by(Mod.sort))) == before


async def test_a_new_mod_reaches_the_paid_plans_and_a_retired_one_leaves_every_plan(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    free, pro = await person(engine), await person(engine, "Pro")
    async with engine.begin() as conn:
        await conn.execute(insert(Mod).values(slug="glyphh-next", name="Next", description="Soon", free=False, sort=9))
        await conn.execute(update(Mod).where(Mod.slug == "glyphh-workspaces").values(active=False))
    try:
        lic = (await client.get("/v1/license", headers=pro.headers)).json()["payload"]
        assert lic["mods"] == ["glyphh", "glyphh-next", "glyphh-programs", "glyphh-rpa"]
        free_mods = (await client.get("/v1/me", headers=free.headers)).json()["plan"]["mods"]
        assert free_mods == ["glyphh", "glyphh-programs"]
        listed = {m["slug"]: m["plans"] for m in (await client.get("/v1/mods")).json()}
        assert listed == {
            "glyphh": ["Free", "Pro", "Team"],
            "glyphh-rpa": ["Pro", "Team"],
            "glyphh-programs": ["Free", "Pro", "Team"],
            "glyphh-next": ["Pro", "Team"],
        }
    finally:
        async with engine.begin() as conn:
            await conn.execute(delete(Mod).where(Mod.slug == "glyphh-next"))
            await conn.execute(update(Mod).where(Mod.slug == "glyphh-workspaces").values(active=True))
