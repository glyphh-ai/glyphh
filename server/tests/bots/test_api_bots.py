"""The bots routes: made, read, changed, scoped and deleted, each org seeing only its own."""

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.conftest import Served, connected, made_bot
from tests.db.helpers import person


async def test_a_bot_is_made_with_a_slug_from_its_name_and_the_defaults(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    look = {
        "head": "round",
        "tail": "curl",
        "eye": "wink",
        "extra": "none",
        "accessory": "bow",
        "pose": "sit",
        "x": "y",
    }
    bot = await made_bot(served, ada, look=look, models=["triage"])
    assert bot["slug"] == "inbox-cat" and bot["model"] == "claude-opus-5-5" and bot["models"] == ["triage"]
    assert bot["look"] == {k: v for k, v in look.items() if k != "x"}
    assert bot["limits"] == {"max_turns": 20, "usd_per_run": 2.0}
    assert bot["connections"] == [] and bot["last_run"] is None
    listed = (await served.http.get("/v1/bots", headers=ada.headers)).json()["bots"]
    assert [b["slug"] for b in listed] == ["inbox-cat"]
    assert (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).json()["id"] == bot["id"]


async def test_a_second_bot_of_the_same_slug_is_a_conflict_but_another_org_may_have_it(
    served: Served, engine: AsyncEngine
) -> None:
    ada, grace = await person(engine), await person(engine)
    await made_bot(served, ada)
    res = await served.http.post("/v1/bots", json={"name": "inbox  cat!"}, headers=ada.headers)
    assert res.status_code == 409 and res.json()["error"]["code"] == "E_CONFLICT"
    await made_bot(served, grace)
    assert (await served.http.get("/v1/bots", headers=grace.headers)).json()["bots"][0]["slug"] == "inbox-cat"


async def test_a_bot_is_changed_and_a_new_name_moves_its_slug(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    body = {"name": "Mail Cat", "model": "claude-haiku-5-5", "limits": {"max_turns": 5, "usd_per_run": 0.5}}
    res = await served.http.patch("/v1/bots/inbox-cat", json=body, headers=ada.headers)
    assert res.status_code == 200, res.text
    bot = res.json()
    assert (bot["slug"], bot["model"], bot["limits"]) == ("mail-cat", "claude-haiku-5-5", body["limits"])
    assert bot["instructions"] == "Answer the mail."
    assert (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).status_code == 404


async def test_a_model_not_on_the_list_is_refused(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await served.http.post("/v1/bots", json={"name": "X", "model": "gpt-9"}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "model"
    models = (await served.http.get("/v1/bots/models", headers=ada.headers)).json()["models"]
    assert [m["id"] for m in models if m["default"]] == ["claude-opus-5-5"]
    assert {m["id"]: m["input_cents_per_mtok"] for m in models}["claude-haiku-5-5"] == 10


async def test_a_bot_is_scoped_per_connection_to_the_tools_it_may_use(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    gmail = await connected(served, ada)
    scopes = {"connections": [{"connection_id": gmail["id"], "tools": ["gmail-send-email", "gmail-send-email"]}]}
    res = await served.http.put("/v1/bots/inbox-cat/connections", json=scopes, headers=ada.headers)
    assert res.status_code == 200, res.text
    assert res.json()["connections"] == [
        {"connection_id": gmail["id"], "app": "gmail", "app_name": "Gmail", "tools": ["gmail-send-email"]}
    ]
    grace = await person(engine)
    await made_bot(served, grace)
    res = await served.http.put("/v1/bots/inbox-cat/connections", json=scopes, headers=grace.headers)
    assert res.status_code == 404  # another org's connection is not theirs to scope


async def test_a_bot_another_org_made_is_not_found_and_a_deleted_one_is_gone(
    served: Served, engine: AsyncEngine
) -> None:
    ada, grace = await person(engine), await person(engine)
    await made_bot(served, ada)
    assert (await served.http.get("/v1/bots/inbox-cat", headers=grace.headers)).status_code == 404
    assert (await served.http.delete("/v1/bots/inbox-cat", headers=grace.headers)).status_code == 404
    assert (await served.http.delete("/v1/bots/inbox-cat", headers=ada.headers)).status_code == 204
    assert (await served.http.get("/v1/bots", headers=ada.headers)).json()["bots"] == []
