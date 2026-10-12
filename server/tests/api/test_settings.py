"""What the platform remembers for a person: the theme, the rail, each list's rows per page."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.helpers import bearer


async def test_settings_start_at_the_defaults_and_change_a_field_at_a_time(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = {"authorization": await bearer(engine, "settings@api.test")}
    first = await client.get("/v1/me/settings", headers=auth)
    assert first.json() == {"theme": "system", "rail_collapsed": False, "page_sizes": {}}
    changed = await client.patch(
        "/v1/me/settings", headers=auth, json={"rail_collapsed": True, "page_sizes": {"members": 25}}
    )
    assert changed.json() == {"theme": "system", "rail_collapsed": True, "page_sizes": {"members": 25}}
    more = await client.patch("/v1/me/settings", headers=auth, json={"theme": "light", "page_sizes": {"usage": 100}})
    assert more.json() == {"theme": "light", "rail_collapsed": True, "page_sizes": {"members": 25, "usage": 100}}
    assert (await client.get("/v1/me/settings", headers=auth)).json() == more.json()


async def test_only_the_drawn_values_are_taken(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    auth = {"authorization": await bearer(engine, "settings-bad@api.test")}
    for body in ({"theme": "neon"}, {"page_sizes": {"members": 30}}, {"rail_collapsed": "maybe"}):
        res = await client.patch("/v1/me/settings", headers=auth, json=body)
        assert res.status_code == 422 and res.json()["error"]["code"] == "E_INVALID"
    assert (await client.get("/v1/me/settings")).status_code == 401
