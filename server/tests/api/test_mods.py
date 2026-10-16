"""The mods catalog: each mod in the plans whose newest version names it in mod_limits, or sold as an add-on; a retired
mod in none, and a mod no longer seeded retired."""

import httpx
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.schema import apply_schema
from glyphh_server.models import Mod
from tests.conftest import SETTINGS
from tests.db.helpers import person, with_addon


async def test_the_catalog_lists_each_mod_and_the_plans_that_include_it(client: httpx.AsyncClient) -> None:
    res = await client.get("/v1/mods")
    assert res.status_code == 200
    mods = res.json()
    assert [(m["slug"], m["name"], m["plans"]) for m in mods] == [
        ("programs", "Programs", []),
        ("gateway", "Gateway", []),
        ("ada", "Ada", []),
    ]
    assert all(m["description"] for m in mods)
    assert [m["addon"] for m in mods] == [
        {"price_cents": cents, "per_seat": True, "plans": ["Pro", "Team"], "free": False} for cents in (400, 400, 400)
    ]


async def test_seeding_again_keeps_the_catalog(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        before = list(await conn.execute(select(Mod).order_by(Mod.sort)))
    await apply_schema(engine, SETTINGS)
    async with engine.connect() as conn:
        assert list(await conn.execute(select(Mod).order_by(Mod.sort))) == before


async def test_a_retired_mod_leaves_every_plan_and_a_mod_no_longer_seeded_is_retired(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    pro = await person(engine, "Pro")
    await with_addon(engine, pro.org_id, "gateway")
    async with engine.begin() as conn:
        await conn.execute(insert(Mod).values(slug="glyphh-old", name="Old", description="Gone", sort=9))
        await conn.execute(update(Mod).where(Mod.slug == "gateway").values(active=False))
    try:
        await apply_schema(engine, SETTINGS)
        lic = (await client.get("/v1/license", headers=pro.headers)).json()["payload"]
        assert list(lic["mods"]) == []
        slugs = [m["slug"] for m in (await client.get("/v1/mods")).json()]
        assert slugs == ["programs", "ada"]
        assert "gateway" not in [a["mod"] for a in (await client.get("/v1/addons", headers=pro.headers)).json()]
        async with engine.connect() as conn:
            assert (await conn.execute(select(Mod.active).where(Mod.slug == "glyphh-old"))).scalar_one() is False
    finally:
        async with engine.begin() as conn:
            await conn.execute(delete(Mod).where(Mod.slug == "glyphh-old"))
            await conn.execute(update(Mod).where(Mod.slug == "gateway").values(active=True))
