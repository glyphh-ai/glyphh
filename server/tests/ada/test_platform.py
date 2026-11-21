"""What the platform needs of Ada Cloud: the account API says Ada is on, the platform's own sign-in (an OAuth access
token, kept in its session) reaches the Ada host, and the org's usage against its plan."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from tests.ada.conftest import a_model
from tests.connector import granted
from tests.db.helpers import person


async def test_the_account_api_says_ada_cloud_is_on(engine: AsyncEngine, ada: httpx.AsyncClient) -> None:
    who = await person(engine)
    me = await ada.get("http://api.test/v1/me", headers=who.headers)
    assert me.json()["ada_cloud"] is True
    renamed = await ada.patch("http://api.test/v1/me", json={"name": "Ada"}, headers=who.headers)
    assert renamed.json()["ada_cloud"] is True


async def test_the_platforms_sign_in_reads_usage_against_the_plan(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Pro")
    _, platform = await granted(engine, who)
    empty = (await ada.get("/v1/usage", headers=platform)).json()
    assert (empty["plan"], empty["models"], empty["precedents"]) == ("Pro", 0, {"used": 0, "max": 100_000})
    assert empty["requests"] == {"used": 0, "max": 1_000_000, "over": 0, "overage": True}
    await a_model(ada, platform, n=12)
    await a_model(ada, platform, name="other", n=3)
    used = (await ada.get("/v1/usage", headers=platform)).json()
    assert (used["models"], used["precedents"]) == (2, {"used": 15, "max": 100_000})


async def test_a_plan_without_a_cap_has_none(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    who = await person(engine, "Enterprise")
    usage = (await ada.get("/v1/usage", headers=who.headers)).json()
    assert (usage["plan"], usage["precedents"]["max"]) == ("Enterprise", None)
