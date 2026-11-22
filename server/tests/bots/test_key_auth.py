"""The bots' routes take a person's live Ada API key as well as their sign-in (api/key_auth.py), so their own code
(the SDK's bots client) reaches their bots with the key it reaches Ada with; an unknown or revoked key, and a bot's
own Ada key (held where the bot runs), are refused."""

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import keys
from glyphh_server.db import tenancy
from tests.bots.conftest import Served, made_bot
from tests.db.helpers import Person, person
from tests.link import principal


async def _key(engine: AsyncEngine, who: Person) -> tuple[str, object]:
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        made = await keys.create(conn, principal(who), "my script", None, 1.0)
    return made.key, made.id


async def test_a_persons_ada_key_reaches_their_bots(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    key, key_id = await _key(engine, ada)
    bearer = {"authorization": f"Bearer {key}"}
    listed = await served.http.get("/v1/bots", params={"q": "inbox"}, headers=bearer)
    assert listed.status_code == 200 and [b["slug"] for b in listed.json()["bots"]] == ["inbox-cat"]
    run = await served.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=bearer)
    assert run.status_code == 202, run.text
    await served.settled()
    assert (await served.http.get("/v1/bot-approvals", headers=bearer)).json()["runs"][0]["id"] == run.json()["id"]
    assert (await served.http.get("/v1/bot-templates", headers=bearer)).status_code == 200
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        await keys.revoke(conn, principal(ada), key_id)
    assert (await served.http.get("/v1/bots", headers=bearer)).status_code == 401


async def test_an_unknown_key_and_a_bots_own_key_are_refused(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    await served.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)
    await served.settled()
    own = served.ada.keys[0]  # the bot's own Ada key, as its gates use it
    for key in ("glyphh_ak_nope", own):
        for path in ("/v1/bots", "/v1/bot-approvals"):
            res = await served.http.get(path, headers={"authorization": f"Bearer {key}"})
            assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED", res.text
        res = await served.http.post(
            "/v1/bots/inbox-cat/runs", json={"input": "x"}, headers={"authorization": f"Bearer {key}"}
        )
        assert res.status_code == 401
    assert (await served.http.get("/v1/bots", headers=ada.headers)).status_code == 200  # a sign-in still is
