"""Where a bot runs: Glyphh cloud by default or one of the org's own rrotors (another org's refused), listed with
whether each is linked right now; until runs are sent to rrotors, starting a run of a bot on one is refused (409
runs_on_pending), and set back on Glyphh cloud it runs. A rrotor deleted puts its bots back on the cloud."""

from datetime import timedelta

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Rrotor
from glyphh_server.ops.bots import due
from tests.bots.conftest import Served, made_bot
from tests.bots.test_schedules import _due, _runs, quiet  # noqa: F401 (quiet: no bot left due after a test)
from tests.connector import granted, tool
from tests.db.helpers import person
from tests.link import local_runtime, self_runtime


async def test_the_places_are_glyphh_cloud_and_the_orgs_rrotors(served: Served, engine: AsyncEngine) -> None:
    ada, other = await person(engine), await person(engine)
    cloud = {"id": None, "name": "Glyphh cloud", "mode": "cloud", "linked": True}
    res = await served.http.get("/v1/bots/places", headers=ada.headers)
    assert res.status_code == 200 and res.json() == {"places": [cloud]}
    acme, mine = await self_runtime(engine, ada), await local_runtime(engine, ada)
    await self_runtime(engine, other, "https://rrotor.other.test")
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == mine.id).values(state="online"))
    shown = (await served.http.get("/v1/bots/places", headers=ada.headers)).json()["places"]
    assert shown == [
        cloud,
        {"id": str(acme.id), "name": "Acme", "mode": "self", "linked": False},
        {"id": str(mine.id), "name": "Mac", "mode": "local", "linked": True},
    ]
    _, auth = await granted(engine, ada)
    said = (await tool(served.http, auth, "bot_places"))["content"][0]["text"]
    assert "Glyphh cloud (cloud): none" in said and f"Acme (self, offline): {acme.id}" in said


async def test_a_bot_on_a_rrotor_waits_for_runs_on_rrotors(served: Served, engine: AsyncEngine) -> None:
    ada, other = await person(engine), await person(engine)
    theirs = await self_runtime(engine, other, "https://rrotor.other.test")
    gmail_bot = await made_bot(served, ada)
    res = await served.http.patch("/v1/bots/inbox-cat", json={"runs_on": str(theirs.id)}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "runs_on"
    acme = await self_runtime(engine, ada)
    res = await served.http.patch("/v1/bots/inbox-cat", json={"runs_on": str(acme.id)}, headers=ada.headers)
    assert res.status_code == 200 and res.json()["runs_on"] == str(acme.id)
    run = await served.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)
    assert run.status_code == 409 and run.json()["error"]["reason"] == "runs_on_pending"
    assert "running bots on your machines is coming" in run.json()["error"]["message"]

    await served.http.patch("/v1/bots/inbox-cat", json={"schedule": {"every": "hour"}}, headers=ada.headers)
    await _due(engine, ada, timedelta(minutes=1))
    assert await due.fire(served.app.state.bots) == 0 and await _runs(engine, ada) == []  # its schedule waits too

    res = await served.http.patch("/v1/bots/inbox-cat", json={"runs_on": None}, headers=ada.headers)
    assert res.json()["runs_on"] is None
    run = await served.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)
    assert run.status_code == 202 and gmail_bot["runs_on"] is None
    await served.settled()


async def test_a_bot_is_made_on_a_rrotor_and_back_on_the_cloud_when_it_goes(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    acme = await self_runtime(engine, ada)
    made = await made_bot(served, ada, runs_on=str(acme.id))
    assert made["runs_on"] == str(acme.id)
    _, auth = await granted(engine, ada)
    assert f"runs on rrotor {acme.id}" in (await tool(served.http, auth, "bot", slug="inbox-cat"))["content"][0]["text"]
    async with engine.begin() as conn:
        await conn.execute(delete(Rrotor).where(Rrotor.id == acme.id))
    assert (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).json()["runs_on"] is None
