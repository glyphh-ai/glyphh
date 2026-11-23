"""The bots routes: a bot made as an agent (its instructions, standing task, examples, decisions and notes, checked,
every problem said), read, listed after the org's orchestrator, changed (the slug stays), scoped and deleted (its Ada
key revoked), each org seeing only its own. A spec that is still a loop of steps is refused, saying so."""

from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotPlugin, RuntimeKey
from glyphh_server.ops.bots import store
from tests.bots.conftest import TOOLS, Served, connected, inbox, made_bot
from tests.bots.remote import online
from tests.db.helpers import Person, person

LOOK = {"head": "round", "tail": "curl", "eye": "wink", "extra": "none", "accessory": "bow", "pose": "sit", "x": "y"}
PLAIN: dict[str, Any] = {"name": "Poet", "instructions": "Write poems.", "spec": {}}


async def post(s: Served, who: Person, **over: Any) -> Any:
    return await s.http.post("/v1/bots", json={**PLAIN, **over}, headers=who.headers)


async def patch(s: Served, who: Person, slug: str, **body: Any) -> Any:
    return await s.http.patch(f"/v1/bots/{slug}", json=body, headers=who.headers)


async def test_a_bot_is_made_with_a_slug_from_its_name_and_its_own_ada_key(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    bot = await made_bot(served, ada, look=LOOK, examples=["  Anything worth answering? ", " ", ""])
    assert bot["slug"] == "inbox-cat" and bot["model"] == "claude-opus-5-5" and bot["role"] == "bot"
    assert bot["look"] == {k: v for k, v in LOOK.items() if k != "x"}
    assert bot["gate_models"] == ["bot-inbox-cat-gate-worth", "bot-inbox-cat-memory", "bot-inbox-cat-instructions",
                                  "bot-inbox-cat-personality"]  # fmt: skip
    assert [c["tools"] for c in bot["connections"]] == [TOOLS] and bot["last_run"] is None
    assert sorted(bot["spec"]) == ["gates", "seed"] and "replies" in bot["skills"]
    assert bot["task"] == "Answer the mail worth answering." and bot["examples"] == ["Anything worth answering?"]
    assert bot["plugins"] == [{"name": "notes", "version": "1.0.0", "latest": "1.0.0", "source": "personal"}]
    assert bot["can_run_on"] == ["cloud", "rrotor"] and bot["runs_on"] is None
    listed = (await served.http.get("/v1/bots", headers=ada.headers)).json()["bots"]
    assert [(b["slug"], b["role"]) for b in listed] == [("orchestrator", "orchestrator"), ("inbox-cat", "bot")]
    found = (await served.http.get("/v1/bots", params={"q": "mail WORTH"}, headers=ada.headers)).json()["bots"]
    assert [b["slug"] for b in found] == ["inbox-cat"]
    assert (await served.http.get("/v1/bots", params={"q": "100%"}, headers=ada.headers)).json()["bots"] == []
    assert (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).json()["id"] == bot["id"]
    assert (await served.http.get("/v1/bots/nope", headers=ada.headers)).status_code == 404
    async with engine.begin() as conn:
        mine = (RuntimeKey.name == "bot inbox-cat", RuntimeKey.user_id == ada.user_id)  # made as the person
        key = (await conn.execute(select(RuntimeKey).where(*mine))).one()
    assert key.revoked_at is None
    assert (await served.http.delete("/v1/bots/inbox-cat", headers=ada.headers)).status_code == 204
    async with engine.begin() as conn:
        assert (await conn.execute(select(RuntimeKey.revoked_at).where(RuntimeKey.id == key.id))).scalar() is not None
    left = (await served.http.get("/v1/bots", headers=ada.headers)).json()["bots"]
    assert [b["slug"] for b in left] == ["orchestrator"]


async def test_a_bot_with_nothing_but_its_instructions_is_a_bot(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await post(served, ada)
    assert res.status_code == 201, res.text
    bot = res.json()
    assert (bot["task"], bot["examples"], bot["plugins"], bot["spec"], bot["skills"]) == ("", [], [], {}, {})
    assert bot["gate_models"] == ["bot-poet-memory", "bot-poet-instructions", "bot-poet-personality"]


async def test_a_loop_of_steps_is_no_longer_a_bot(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    loop = {"loop": [{"id": "mail", "run": "gmail-find-email"}], "gates": inbox()["gates"]}
    res = await post(served, ada, spec=loop)
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "spec" and err["problems"] == [store.NO_LOOP]
    assert err["message"].startswith("A bot is no longer a loop of steps: say what it does in its instructions")
    res = await post(served, ada, spec={"takes": "text", "try": 2, "hosts": ["hn.algolia.com"]})
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "spec"
    assert err["problems"] == [
        "A bot's spec has gates (decisions), hosts, builtins, limits and seed: takes, try is not one."
    ]
    await made_bot(served, ada)
    res = await patch(served, ada, "inbox-cat", spec=loop)  # nor may a bot be changed back into one
    assert res.status_code == 422 and res.json()["error"]["problems"] == [store.NO_LOOP]


async def test_a_bot_that_does_not_fit_is_refused_saying_why(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await post(served, ada, spec={"hosts": ["localhost"]})
    assert res.status_code == 422 and res.json()["error"]["reason"] == "hosts"
    seeded = inbox()
    seeded["gates"]["worth"]["seed_from"] = "nope"
    res = await post(served, ada, spec=seeded)
    assert res.status_code == 422 and "worth: nope is not one" in res.json()["error"]["message"]
    no_outcomes = inbox()
    del no_outcomes["gates"]["worth"]["outcomes"]
    res = await post(served, ada, spec=no_outcomes)
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "spec" and err["problems"] and "worth" in err["problems"][0]
    res = await post(served, ada, skills={"Bad Name": "x"})
    assert res.status_code == 422 and res.json()["error"]["reason"] == "skills"
    for name in ("!!!", "1234"):
        res = await post(served, ada, name=name)
        assert res.status_code == 422 and res.json()["error"]["reason"] == "name", name
    res = await post(served, ada, model="gpt-9")
    assert res.status_code == 422 and res.json()["error"]["reason"] == "model"
    models = (await served.http.get("/v1/bots/models", headers=ada.headers)).json()["models"]
    assert [m["id"] for m in models if m["default"]] == ["claude-opus-5-5"]
    res = await post(served, ada, name="9 A name far, far too long for its Ada models")
    assert res.status_code == 201 and res.json()["slug"] == "a-name-far-far-too-long-for-it"


async def test_a_task_and_examples_have_their_limits_and_a_role_is_never_given(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    assert (await post(served, ada, task="x" * 4001)).status_code == 422
    assert (await post(served, ada, examples=["Hi"] * 7)).status_code == 422
    res = await post(served, ada, examples=["Fine", "y" * 201])
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "examples"
    assert err["message"] == f"An example prompt is at most 200 characters: {'y' * 40}… is longer."
    for role in ("orchestrator", "bot"):
        assert (await post(served, ada, role=role)).status_code == 422
    made = await post(served, ada, task="  Write a poem.  ", examples=[" One ", "y" * 200])
    assert made.status_code == 201 and made.json()["task"] == "Write a poem."
    assert made.json()["examples"] == ["One", "y" * 200]
    assert (await patch(served, ada, "poet", role="orchestrator")).status_code == 422
    assert (await patch(served, ada, "poet", task="x" * 4001)).status_code == 422
    assert (await patch(served, ada, "poet", examples=["y" * 201])).json()["error"]["reason"] == "examples"
    changed = await patch(served, ada, "poet", task="A haiku.", examples=[" Two ", ""])
    assert (changed.json()["task"], changed.json()["examples"], changed.json()["role"]) == ("A haiku.", ["Two"], "bot")


async def test_a_second_bot_of_the_same_slug_is_a_conflict_but_another_org_may_have_it(
    served: Served, engine: AsyncEngine
) -> None:
    ada, grace = await person(engine), await person(engine)
    await made_bot(served, ada)
    res = await post(served, ada, name="inbox  cat!")
    assert res.status_code == 409 and res.json()["error"]["code"] == "E_CONFLICT"
    await made_bot(served, grace)
    assert (await served.http.get("/v1/bots", headers=grace.headers)).json()["bots"][1]["slug"] == "inbox-cat"
    assert (await served.http.get("/v1/bots/inbox-cat", headers=grace.headers)).json()["id"] != ""


async def test_a_bot_is_changed_and_checked_again_its_slug_staying(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada, look=LOOK, voice="af_heart")
    body = {"name": "Mail Cat", "model": "claude-haiku-5-5", "look": {"eye": "big", "x": "y"}, "summary": None}
    res = await patch(served, ada, "inbox-cat", **body, effort="high", permission_mode="auto")
    assert res.status_code == 200, res.text
    bot = res.json()
    assert (bot["slug"], bot["name"], bot["model"], bot["look"]) == ("inbox-cat", "Mail Cat", "claude-haiku-5-5",
                                                                     {"eye": "big"})  # fmt: skip
    assert bot["summary"] == "Answers the mail worth answering" and bot["voice"] == "af_heart"
    assert (bot["effort"], bot["permission_mode"]) == ("high", "auto")
    cleared = (await patch(served, ada, "inbox-cat", look=None, voice=None, model=None, mascot=None)).json()
    assert (cleared["look"], cleared["voice"], cleared["model"], cleared["mascot"]) == ({}, "", "claude-opus-5-5", "")
    bad = inbox()
    del bad["gates"]["worth"]["outcomes"]
    res = await patch(served, ada, "inbox-cat", spec=bad)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "spec"
    res = await patch(served, ada, "inbox-cat", skills={}, spec={})
    assert (res.json()["plugins"], res.json()["gate_models"][0]) == ([], "bot-inbox-cat-memory")
    assert (await patch(served, ada, "nope", name="X")).status_code == 404


async def test_a_bots_schedule_folders_and_place_are_changed(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await online(engine, ada)
    await made_bot(served, ada)
    res = await patch(served, ada, "inbox-cat", schedule={"every": "day", "at": "09:00"})
    assert res.json()["schedule_summary"].startswith("Every day at 9:00") and res.json()["next_run_at"] is not None
    there = await patch(served, ada, "inbox-cat", runs_on=str(rt.id), folders=[{"path": "/data/", "access": "read"}])
    assert there.status_code == 200, there.text
    assert (there.json()["runs_on"], there.json()["folders"]) == (str(rt.id), [{"path": "/data", "access": "read"}])
    kept = await patch(served, ada, "inbox-cat", summary="Keeps the inbox")  # what is not given stays
    assert (kept.json()["runs_on"], kept.json()["folders"][0]["path"]) == (str(rt.id), "/data")
    bad = await patch(served, ada, "inbox-cat", folders=[{"path": "data", "access": "read"}])
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "folders"
    back = await patch(served, ada, "inbox-cat", runs_on=None, folders=[])
    assert (back.json()["runs_on"], back.json()["folders"]) == (None, [])


async def test_a_bot_whose_plugin_needs_a_rrotor_is_not_put_on_glyphh_cloud(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    rt = await online(engine, ada)
    bot = await made_bot(served, ada, runs_on=str(rt.id))
    files = {"glyphh.json": '{"folders": true}'}
    values = {"org_id": ada.org_id, "bot_id": bot["id"], "name": "filer", "version": "1.0.0", "files": files}
    async with engine.begin() as conn:
        await conn.execute(insert(BotPlugin).values(**values, source="template:filer"))
    shown = (await served.http.get("/v1/bots/inbox-cat", headers=ada.headers)).json()
    assert shown["can_run_on"] == ["rrotor"]
    assert shown["plugins"][0] == {"name": "filer", "version": "1.0.0", "latest": "1.0.0", "source": "template:filer"}
    res = await patch(served, ada, "inbox-cat", runs_on=None)
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "runs_on"
    assert err["message"] == store.NEEDS_RROTOR.format(name="Inbox Cat")
    assert err["message"].startswith("Inbox Cat needs a rrotor: it cannot run on Glyphh cloud.")
    still = await patch(served, ada, "inbox-cat", name="Filing Cat")  # anything else of it is changed as ever
    assert (still.status_code, still.json()["runs_on"], still.json()["name"]) == (200, str(rt.id), "Filing Cat")


async def test_scopes_are_per_connection_and_only_the_orgs_own(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    gmail = await connected(served, ada, "apn_2")
    scopes = {"connections": [{"connection_id": gmail["id"], "tools": TOOLS + TOOLS}]}
    res = await served.http.put("/v1/bots/inbox-cat/connections", json=scopes, headers=ada.headers)
    assert res.status_code == 200, res.text
    assert res.json()["connections"] == [{"connection_id": gmail["id"], "app": "gmail", "app_name": "Gmail",
                                          "tools": TOOLS}]  # fmt: skip
    none = await served.http.put("/v1/bots/inbox-cat/connections", json={"connections": []}, headers=ada.headers)
    assert none.status_code == 200 and none.json()["connections"] == []  # a bot with no tools still answers
    grace = await person(engine)
    await made_bot(served, grace)
    res = await served.http.put("/v1/bots/inbox-cat/connections", json=scopes, headers=grace.headers)
    assert res.status_code == 404  # another org's connection is not theirs to scope
    assert (await served.http.delete("/v1/bots/nope", headers=grace.headers)).status_code == 404


async def test_what_a_bot_may_be_given_is_listed_its_voices_places_key_and_what_it_learned(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    voices = (await served.http.get("/v1/bots/voices", headers=ada.headers)).json()
    assert voices["samples"] is False and [v["id"] for v in voices["voices"] if v["default"]] == ["af_heart"]
    rt = await online(engine, ada)
    places = (await served.http.get("/v1/bots/places", headers=ada.headers)).json()["places"]
    assert [(p["id"], p["mode"], p["linked"]) for p in places] == [(None, "cloud", True), (str(rt.id), "self", True)]
    ticket = await served.http.post(f"/v1/bots/places/{rt.id}/ticket", headers=ada.headers)
    assert ticket.status_code == 200 and ticket.json()["expires_in"] == 600 and ticket.json()["url"] == places[1]["url"]
    key = (await served.http.get("/v1/bot-key", headers=ada.headers)).json()
    assert key == {"set": False, "hint": "", "set_at": None, "glyphh_key": True}
    learned = await served.http.get("/v1/bots/inbox-cat/gates", headers=ada.headers)
    assert learned.status_code == 200 and list(learned.json()["gates"]) == ["worth"]
