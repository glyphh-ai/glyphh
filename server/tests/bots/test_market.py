"""The bots marketplace (docs/specs/bot-agent-loop.md, 7): the templates Glyphh ships, each a plugin package, listed,
searched and read; one installed into an org as its own bot once its apps are connected (its plugin kept, its
standing task, examples and decisions with it); a template that runs only on a rrotor said so and installed only
onto a linked one; and the same through the connector."""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.bots import packages, templates
from glyphh_server.ops.bots.agent.turn import Ended, Turn
from tests.bots.agents import SESSION
from tests.bots.conftest import Served, connected, made_bot, ran
from tests.bots.market import TIDY, bot_of, installed, linked, rrotor_only, shelved
from tests.bots.remote import online
from tests.connector import granted, rpc, tool
from tests.db.helpers import Person, person

# each template Glyphh ships: the apps it needs, what it decides, how often it runs on its own
SHIPPED: dict[str, tuple[list[str], list[str], str]] = {
    "inbox-triage": (["gmail"], ["worth"], "off"),
    "lead-scoring": (["google_sheets"], ["score"], "off"),
    "meeting-prep": (["google_calendar", "notion"], ["prep"], "off"),
    "news-brief": ([], ["read"], "off"),
    "pr-review-digest": (["github", "slack"], ["today"], "off"),
    "resume-screener": (["gmail"], ["source", "fit", "made"], "hour"),
    "support-triage": (["gmail", "slack"], ["urgency"], "off"),
    "weekly-report": (["github", "notion"], ["ready"], "off"),
}
KEYS: set[str] = {
    *("slug", "version", "name", "summary", "description", "look", "apps", "decides", "examples", "task"),
    *("schedule", "runs_on"),
}
ANYWHERE: list[str] = ["cloud", "rrotor"]
SETUP: str = "http://localhost:3000/runtimes"


async def test_the_templates_are_listed_searched_and_read(served: Served, ana: Person) -> None:
    listed = (await served.http.get("/v1/bot-templates", headers=ana.headers)).json()["templates"]
    assert [t["slug"] for t in listed] == sorted(SHIPPED) and all(set(t) == KEYS for t in listed)
    for t in listed:
        apps, decides, every = SHIPPED[t["slug"]]
        assert [a["app"] for a in t["apps"]] == apps and [d["name"] for d in t["decides"]] == decides
        assert t["schedule"]["every"] == every and t["runs_on"] == ANYWHERE and t["version"] == "1.0.0"
        assert t["task"] and 1 <= len(t["examples"]) <= 6 and t["summary"] and t["description"] and t["look"]
    found = (await served.http.get("/v1/bot-templates?q=inbox gmail", headers=ana.headers)).json()["templates"]
    assert [t["slug"] for t in found] == ["inbox-triage"]
    assert (await served.http.get("/v1/bot-templates?q=payroll", headers=ana.headers)).json()["templates"] == []
    res = await served.http.get("/v1/bot-templates/inbox-triage", headers=ana.headers)
    one = res.json()
    assert res.status_code == 200 and one == found[0] and one["name"] == "Inbox Triage"
    assert one["apps"] == [{"app": "gmail", "name": "Gmail", "tools": ["gmail-find-email", "gmail-send-email"]}]
    assert one["decides"] == [{"name": "worth", "question": "Worth your time?", "outcomes": ["read", "skip"]}]
    assert one["examples"][0] == "What in my inbox is worth my time?" and one["task"].startswith("Read my unread mail")
    sheets = (await served.http.get("/v1/bot-templates/lead-scoring", headers=ana.headers)).json()
    assert sheets["apps"][0]["name"] == "Google Sheets"  # an app's name, from its slug
    res = await served.http.get("/v1/bot-templates/nope", headers=ana.headers)
    assert res.status_code == 404 and res.json()["error"]["message"] == "There is no such bot template."
    assert (await served.http.get("/v1/bot-templates")).status_code == 401


@pytest.mark.parametrize("slug", sorted(SHIPPED))
async def test_each_template_installs_into_a_bot_with_its_plugin(served: Served, ana: Person, slug: str) -> None:
    apps, decides, every = SHIPPED[slug]
    side = packages.library()[slug].sidecar
    mine = await linked(served, ana, *apps)
    bot = await installed(served, ana, slug)
    assert (bot["slug"], bot["name"], bot["summary"]) == (slug, side.bot.name, side.bot.tagline)
    assert (bot["model"], bot["effort"], bot["role"]) == (side.bot.model, "medium", "bot")
    assert bot["instructions"] == side.bot.instructions and bot["look"] == side.bot.look
    assert bot["task"] == side.task and bot["examples"] == side.examples and bot["skills"] == {}
    assert sorted(bot["spec"].get("gates", {})) == sorted(decides) and bot["spec"].get("gates", {}) == side.decisions
    assert bot["spec"].get("hosts", []) == side.hosts and bot["spec"].get("builtins", []) == side.builtins
    assert bot["spec"].get("limits", {}) == side.limits and "loop" not in bot["spec"]
    assert sorted(bot["gate_models"][: len(decides)]) == sorted(f"bot-{slug}-gate-{d}" for d in decides)
    assert bot["plugins"] == [{"name": slug, "version": "1.0.0", "latest": "1.0.0", "source": f"template:{slug}"}]
    assert bot["can_run_on"] == ANYWHERE and bot["runs_on"] is None and bot["folders"] == []
    assert bot["schedule"]["every"] == every and (bot["next_run_at"] is not None) == (every != "off")
    assert [(c["app"], c["connection_id"], c["tools"]) for c in bot["connections"]] == [
        (r.app, mine[r.app]["id"], sorted(r.tools)) for r in side.requires
    ]
    assert [t["name"] for t in bot["connector_tools"]] == [t["name"] for t in side.connector_tools]
    assert await bot_of(served, ana, slug) == bot


async def test_a_template_is_refused_until_its_apps_are_connected_and_is_the_orgs_own(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    res = await served.http.post("/v1/bot-templates/support-triage/install", json={}, headers=ana.headers)
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "connections" and err["apps"] == ["gmail", "slack"]
    assert err["message"] == "Connect gmail, slack first: the bot uses it."
    await linked(served, ana, "gmail")
    res = await served.http.post("/v1/bot-templates/support-triage/install", json={}, headers=ana.headers)
    assert res.status_code == 422 and res.json()["error"]["apps"] == ["slack"]
    res = await served.http.post("/v1/bot-templates/nope/install", json={}, headers=ana.headers)
    assert res.status_code == 404 and res.json()["error"]["slug"] == "nope"
    await linked(served, ana, "gmail", n=2)  # a second Gmail account: the bot uses the org's first
    bot = await installed(served, ana, "inbox-triage", name="Mail")
    held = (await served.http.get("/v1/connections", headers=ana.headers)).json()["connections"]
    first = next(c for c in held if c["account_id"] == "apn_gmail_1")
    assert (bot["slug"], bot["name"], bot["gate_models"][0]) == ("mail", "Mail", "bot-mail-gate-worth")
    assert bot["connections"][0]["connection_id"] == first["id"]
    again = await served.http.post("/v1/bot-templates/inbox-triage/install", json={"name": "Mail"}, headers=ana.headers)
    assert again.status_code == 409  # its slug is taken: named another way, it is a second bot
    assert (await installed(served, ana, "inbox-triage"))["slug"] == "inbox-triage"
    served.pd.accounts.clear()
    grace = await person(engine)  # another org has neither ana's connection nor her bot
    res = await served.http.post("/v1/bot-templates/inbox-triage/install", json={}, headers=grace.headers)
    assert res.status_code == 422 and res.json()["error"]["apps"] == ["gmail"]
    assert (await served.http.get("/v1/bots/mail", headers=grace.headers)).status_code == 404
    res = await served.http.patch("/v1/bots/mail", json={"instructions": "Mine now."}, headers=ana.headers)
    assert res.status_code == 200 and "Mine now." not in packages.library()["inbox-triage"].sidecar.bot.instructions


async def test_an_installed_template_runs_with_its_plugins_skills(served: Served, ana: Person) -> None:
    await connected(served, ana)
    bot = await installed(served, ana, "inbox-triage")
    seen: dict[str, Any] = {}

    async def go(turn: Turn) -> Ended:
        seen["skill"] = (turn.plugins[0] / "skills" / "digest" / "SKILL.md").read_text()
        seen["manifest"] = (turn.plugins[0] / ".claude-plugin" / "plugin.json").exists()
        return Ended(text="Nothing unread is worth your time.", session=SESSION, input_tokens=5, output_tokens=5)

    served.agent.script = [go]
    run = await ran(served, ana, bot["slug"])
    assert run["status"] == "done" and run["output"] == "Nothing unread is worth your time."
    turn = served.agent.turns[0]
    assert turn.message == bot["task"] and turn.skills == ["inbox-triage:digest"]
    assert [p.name for p in turn.plugins] == ["inbox-triage"] and seen["manifest"]
    assert seen["skill"] == packages.library()["inbox-triage"].files["skills/digest/SKILL.md"]
    assert sorted(t.name for t in turn.tools) == ["ask_person", "decide", "gmail_find_email", "gmail_send_email"]
    assert "You are Inbox Triage" in turn.system and "Worth your time?" in turn.system and "digest" in turn.system


async def test_a_template_that_runs_only_on_a_rrotor_installs_onto_a_linked_one(
    served: Served, ana: Person, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    shelved(monkeypatch, rrotor_only())
    one = (await served.http.get(f"/v1/bot-templates/{TIDY}", headers=ana.headers)).json()
    assert one["runs_on"] == ["rrotor"] and one["name"] == "Folder Tidy"
    listed = (await served.http.get("/v1/bot-templates?q=folder", headers=ana.headers)).json()["templates"]
    assert [(t["slug"], t["runs_on"]) for t in listed] == [(TIDY, ["rrotor"])]
    res = await served.http.post(f"/v1/bot-templates/{TIDY}/install", json={}, headers=ana.headers)
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "rrotor" and err["setup_url"] == SETUP
    assert err["message"] == (
        "Folder Tidy needs a rrotor: it cannot run on Glyphh cloud. Set one up, link it, then install it."
    )
    off = await online(engine, ana, state="stopped")  # one of the org's, but not linked now
    res = await served.http.post(f"/v1/bot-templates/{TIDY}/install", json={}, headers=ana.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "rrotor"
    rt = await online(engine, ana)
    bot = await installed(served, ana, TIDY)
    assert bot["runs_on"] == str(rt.id) != str(off.id) and bot["can_run_on"] == ["rrotor"]
    assert bot["plugins"] == [{"name": TIDY, "version": "1.0.0", "latest": "1.0.0", "source": f"template:{TIDY}"}]
    res = await served.http.patch(f"/v1/bots/{TIDY}", json={"runs_on": None}, headers=ana.headers)
    err = res.json()["error"]
    assert res.status_code == 422 and err["reason"] == "runs_on" and "Folder Tidy needs a rrotor" in err["message"]
    assert (await bot_of(served, ana, TIDY))["runs_on"] == str(rt.id)  # refused: it is where it was
    res = await served.http.patch(f"/v1/bots/{TIDY}", json={"runs_on": str(off.id)}, headers=ana.headers)
    assert res.status_code == 200 and res.json()["runs_on"] == str(off.id)  # another rrotor of the org's is fine


async def test_a_template_that_needs_folders_runs_only_on_a_rrotor(
    served: Served, ana: Person, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    shelved(monkeypatch, rrotor_only(folders=True))
    assert templates.one(TIDY).runs_on == ["rrotor"]
    rt = await online(engine, ana)
    bot = await installed(served, ana, TIDY)
    assert bot["runs_on"] == str(rt.id) and bot["can_run_on"] == ["rrotor"] and bot["folders"] == []


async def test_the_marketplace_through_the_connector(
    served: Served, ana: Person, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    shelved(monkeypatch, rrotor_only())
    _, auth = await granted(engine, ana)
    found = (await tool(served.http, auth, "bot_templates", q="inbox"))["content"][0]["text"]
    assert found == (
        "Inbox Triage (inbox-triage): Picks the unread mail worth your time and sends you a short digest of it; "
        "needs Gmail; runs on Glyphh cloud or a rrotor"
    )
    every = await tool(served.http, auth, "bot_templates")
    assert len(every["structuredContent"]["templates"]) == len(SHIPPED) + 1
    said = every["content"][0]["text"].splitlines()
    tidy_line = next(line for line in said if line.startswith("Folder Tidy"))
    assert tidy_line.endswith("needs no connection; runs on a rrotor only")
    assert (await tool(served.http, auth, "bot_templates", q="zzz"))["content"][0]["text"] == "No such bot template."
    read = await tool(served.http, auth, "bot_template", slug="inbox-triage")
    text = read["content"][0]["text"]
    assert "needs Gmail; runs on Glyphh cloud or a rrotor.\nReads your unread Gmail" in text
    assert "\nDecides: worth (read, skip)\nTry: What in my inbox is worth my time? | " in text
    assert read["structuredContent"]["runs_on"] == ANYWHERE and set(read["structuredContent"]) == KEYS
    missing = await tool(served.http, auth, "bot_template", slug="nope")
    assert missing["isError"] is True and missing["structuredContent"]["error"]["code"] == "E_NOT_FOUND"
    refused = await tool(served.http, auth, "bot_template_install", slug="inbox-triage")
    assert refused["isError"] is True and refused["structuredContent"]["error"]["apps"] == ["gmail"]
    nowhere = await tool(served.http, auth, "bot_template_install", slug=TIDY)
    err = nowhere["structuredContent"]["error"]
    assert nowhere["isError"] is True and (err["reason"], err["setup_url"]) == ("rrotor", SETUP)
    await connected(served, ana)
    given = {"slug": "inbox-triage", "name": "Mail"}
    added = (await rpc(served.http, auth, "tools/call", name="bot_template_install", arguments=given))["result"]
    assert added["isError"] is False and added["content"][0]["text"].startswith("Added Mail (mail): Picks the unread")
    assert "decides worth" in added["content"][0]["text"] and added["content"][0]["text"].endswith("bot_run runs it.")
    assert added["structuredContent"]["plugins"][0]["source"] == "template:inbox-triage"
    await online(engine, ana)
    tidy = await tool(served.http, auth, "bot_template_install", slug=TIDY)
    assert tidy["isError"] is False and "runs on rrotor" in tidy["content"][0]["text"]
    assert tidy["structuredContent"]["can_run_on"] == ["rrotor"]


async def test_the_orgs_bots_are_found_by_their_words(served: Served, ana: Person, engine: AsyncEngine) -> None:
    _, auth = await granted(engine, ana)
    await made_bot(served, ana)
    await installed(served, ana, "inbox-triage")
    assert "Inbox Cat" in (await tool(served.http, auth, "bots", q="cat"))["content"][0]["text"]
    hits = (await tool(served.http, auth, "bots", q="digest inbox"))["structuredContent"]["bots"]
    assert [b["slug"] for b in hits] == ["inbox-triage"]
    listed = (await served.http.get("/v1/bots?q=50%_", headers=ana.headers)).json()["bots"]
    assert listed == []  # its words are words, never patterns
