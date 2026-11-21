"""The bots routes: made (checked by the SDK, every problem said), read, changed (the slug stays), scoped and deleted
(its Ada key revoked), each org seeing only its own."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import RuntimeKey
from tests.bots.conftest import TOOLS, Served, connected, inbox, made_bot
from tests.db.helpers import person

LOOK = {"head": "round", "tail": "curl", "eye": "wink", "extra": "none", "accessory": "bow", "pose": "sit", "x": "y"}


async def test_a_bot_is_made_with_a_slug_from_its_name_and_its_own_ada_key(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    bot = await made_bot(served, ada, look=LOOK)
    assert bot["slug"] == "inbox-cat" and bot["model"] == "claude-opus-5-5"
    assert bot["look"] == {k: v for k, v in LOOK.items() if k != "x"}
    assert bot["gate_models"] == ["bot-inbox-cat-gate-worth", "bot-inbox-cat-memory", "bot-inbox-cat-instructions",
                                  "bot-inbox-cat-personality"]  # fmt: skip
    assert [c["tools"] for c in bot["connections"]] == [TOOLS] and bot["last_run"] is None
    assert bot["spec"]["loop"][0]["run"] == "gmail-find-email" and "replies" in bot["skills"]
    listed = (await served.http.get("/v1/bots", headers=ada.headers)).json()["bots"]
    assert [b["slug"] for b in listed] == ["inbox-cat"]
    assert (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).json()["id"] == bot["id"]
    async with engine.begin() as conn:
        key = (await conn.execute(select(RuntimeKey).where(RuntimeKey.name == "bot inbox-cat"))).one()
    assert key.revoked_at is None and key.user_id == ada.user_id
    assert (await served.http.delete("/v1/bots/inbox-cat", headers=ada.headers)).status_code == 204
    async with engine.begin() as conn:
        assert (await conn.execute(select(RuntimeKey.revoked_at).where(RuntimeKey.id == key.id))).scalar() is not None
    assert (await served.http.get("/v1/bots", headers=ada.headers)).json()["bots"] == []


async def test_a_bot_the_sdk_would_not_run_is_refused_with_every_problem(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    body = {"name": "Inbox Cat", "instructions": "x", "spec": inbox(), "skills": {"replies": "How"}}  # tools unscoped
    res = await served.http.post("/v1/bots", json=body, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "spec"
    assert res.json()["error"]["problems"] == [
        "step mail: gmail-find-email is neither fetch nor a tool the bot may use (scope it on a connection)",
        "step send: gmail-send-email is neither fetch nor a tool the bot may use (scope it on a connection)",
    ]
    no_approval = inbox()
    del no_approval["loop"][3]["approval"]
    res = await served.http.post("/v1/bots", json={**body, "spec": no_approval, "name": "B"}, headers=ada.headers)
    assert "no step has an approval" in res.json()["error"]["message"]
    fetching = {"hosts": ["localhost"], "loop": [{"id": "page", "run": "fetch", "input": "https://localhost/x"}]}
    res = await served.http.post("/v1/bots", json={**body, "spec": fetching, "name": "C"}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "hosts"
    skills = {"Bad Name": "x"}
    fine = {"loop": [{"id": "a", "agent": "Hi"}]}
    res = await served.http.post("/v1/bots", json={**body, "spec": fine, "skills": skills}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "skills"
    for name in ("!!!", "1234"):
        res = await served.http.post("/v1/bots", json={**body, "spec": fine, "name": name}, headers=ada.headers)
        assert res.status_code == 422 and res.json()["error"]["reason"] == "name", name
    long = {**body, "spec": fine, "skills": {}, "name": "9 A name far, far too long for its Ada models"}
    res = await served.http.post("/v1/bots", json=long, headers=ada.headers)
    assert res.status_code == 201 and res.json()["slug"] == "a-name-far-far-too-long-for-it"


async def test_a_second_bot_of_the_same_slug_is_a_conflict_but_another_org_may_have_it(
    served: Served, engine: AsyncEngine
) -> None:
    ada, grace = await person(engine), await person(engine)
    await made_bot(served, ada)
    body = {"name": "inbox  cat!", "instructions": "x", "spec": {"loop": [{"id": "a", "agent": "Hi"}]}}
    res = await served.http.post("/v1/bots", json=body, headers=ada.headers)
    assert res.status_code == 409 and res.json()["error"]["code"] == "E_CONFLICT"
    await made_bot(served, grace)
    assert (await served.http.get("/v1/bots", headers=grace.headers)).json()["bots"][0]["slug"] == "inbox-cat"
    assert (await served.http.get("/v1/bots/inbox-cat", headers=grace.headers)).json()["id"] != ""


async def test_a_bot_is_changed_and_checked_again_its_slug_staying(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    body = {"name": "Mail Cat", "model": "claude-haiku-5-5", "look": {"eye": "big"}, "summary": None}
    res = await served.http.patch("/v1/bots/inbox-cat", json=body, headers=ada.headers)
    assert res.status_code == 200, res.text
    bot = res.json()
    assert (bot["slug"], bot["name"], bot["model"], bot["look"]) == ("inbox-cat", "Mail Cat", "claude-haiku-5-5",
                                                                     {"eye": "big"})  # fmt: skip
    assert bot["summary"] == "Answers the mail worth answering"
    bad = inbox()
    bad["loop"][1]["gate"] = "nope"
    res = await served.http.patch("/v1/bots/inbox-cat", json={"spec": bad}, headers=ada.headers)
    assert res.status_code == 422 and "no gate nope" in res.json()["error"]["message"]
    res = await served.http.put("/v1/bots/inbox-cat/connections", json={"connections": []}, headers=ada.headers)
    assert res.status_code == 422  # its loop still runs both tools


async def test_a_model_not_on_the_list_is_refused(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    body = {"name": "X", "model": "gpt-9", "instructions": "x", "spec": {"loop": [{"id": "a", "agent": "Hi"}]}}
    res = await served.http.post("/v1/bots", json=body, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "model"
    models = (await served.http.get("/v1/bots/models", headers=ada.headers)).json()["models"]
    assert [m["id"] for m in models if m["default"]] == ["claude-opus-5-5"]


async def test_scopes_are_per_connection_and_only_the_orgs_own(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    gmail = await connected(served, ada, "apn_2")
    scopes = {"connections": [{"connection_id": gmail["id"], "tools": TOOLS + TOOLS}]}
    res = await served.http.put("/v1/bots/inbox-cat/connections", json=scopes, headers=ada.headers)
    assert res.status_code == 200, res.text
    assert res.json()["connections"] == [{"connection_id": gmail["id"], "app": "gmail", "app_name": "Gmail",
                                          "tools": TOOLS}]  # fmt: skip
    grace = await person(engine)
    await made_bot(served, grace)
    res = await served.http.put("/v1/bots/inbox-cat/connections", json=scopes, headers=grace.headers)
    assert res.status_code == 404  # another org's connection is not theirs to scope
    assert (await served.http.delete("/v1/bots/nope", headers=grace.headers)).status_code == 404
