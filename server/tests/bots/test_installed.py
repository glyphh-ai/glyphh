"""A bot's plugins (docs/specs/bot-agent-loop.md, 7.2): what its view says of them (a template's at the version
installed, with the newest Glyphh ships; its own notes last), and a plugin brought up to date: its files replaced,
the decisions, hosts and required tools the new version names added, and nothing the person changed touched."""

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotPlugin
from glyphh_server.ops.bots import packages
from glyphh_server.ops.bots.agent.turn import Ended, Turn
from tests.bots.agents import SESSION
from tests.bots.conftest import Served, connected, made_bot, ran
from tests.bots.market import any_component, bot_of, files_of, installed, linked, remade, shelved
from tests.db.helpers import Person

SLUG: str = "inbox-triage"
NEW_SKILL: str = "---\nname: digest\ndescription: How a digest is written\n---\n\nTwo lines per email now.\n"
URGENT: str = "---\nname: urgent\ndescription: What counts as urgent\n---\n\nAn outage is urgent.\n"
DRAFT, POST = "gmail-create-draft", "slack-send-message"
THEIRS: dict[str, str] = {"name": SLUG, "version": "1.0.0", "latest": "1.0.0", "source": f"template:{SLUG}"}
NOTES: dict[str, str] = {"name": "notes", "version": "1.0.0", "latest": "1.0.0", "source": "personal"}


def newer() -> packages.Package:
    """Inbox Triage 1.1.0: its digest skill rewritten, a skill, a decision, a host, a built-in, a Gmail tool and
    Slack added, and its `worth` decision asked another way."""

    def change(manifest: dict[str, Any], side: dict[str, Any]) -> None:
        manifest["version"] = "1.1.0"
        worth = side["decisions"]["worth"]
        side["decisions"]["urgent"] = {**worth, "question": "Is it urgent?", "outcomes": ["now", "later"]}
        side["decisions"]["worth"] = {**worth, "question": "Worth it, in the new words?"}
        side["hosts"], side["builtins"] = ["hn.algolia.com"], ["inbox_label"]
        side["requires"] = [{"app": "gmail", "tools": ["gmail-find-email", DRAFT]}, {"app": "slack", "tools": [POST]}]
        side["bot"]["instructions"] = "You are Inbox Triage, rewritten."

    files = files_of(SLUG) | {"skills/digest/SKILL.md": NEW_SKILL, "skills/urgent/SKILL.md": URGENT}
    return remade(files, change)


async def update(s: Served, who: Person, slug: str, name: str) -> httpx.Response:
    return await s.http.post(f"/v1/bots/{slug}/plugins/{name}/update", headers=who.headers)


async def test_a_bots_view_says_its_plugins_its_own_notes_last(
    served: Served, ana: Person, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    own = await made_bot(served, ana)
    assert own["plugins"] == [NOTES] and own["can_run_on"] == ["cloud", "rrotor"]
    bare = await made_bot(served, ana, name="Bare Cat", skills={}, connections=[])
    assert bare["plugins"] == []
    bot = await installed(served, ana, SLUG)
    assert bot["plugins"] == [THEIRS]
    note = {"house": "---\nname: house\ndescription: House rules\n---\n\nNo exclamation marks.\n"}
    res = await served.http.patch(f"/v1/bots/{SLUG}", json={"skills": note}, headers=ana.headers)
    assert res.status_code == 200 and res.json()["plugins"] == [THEIRS, NOTES]
    await ran(served, ana, SLUG)
    assert served.agent.turns[-1].skills == ["inbox-triage:digest", "notes:house"]
    async with engine.begin() as conn:  # a plugin that came from somewhere else has no newer version to say
        values = {"org_id": ana.org_id, "bot_id": uuid.UUID(bot["id"]), "name": "acme", "version": "0.3.0"}
        await conn.execute(insert(BotPlugin).values(**values, source="upload:acme", files={"README.md": "Hi"}))
    other = {"name": "acme", "version": "0.3.0", "latest": "0.3.0", "source": "upload:acme"}
    assert (await bot_of(served, ana, SLUG))["plugins"] == [other, THEIRS, NOTES]
    assert (await update(served, ana, SLUG, "acme")).status_code == 404
    shelved(monkeypatch, newer())
    assert (await bot_of(served, ana, SLUG))["plugins"] == [other, THEIRS | {"latest": "1.1.0"}, NOTES]
    shelved(monkeypatch, only=True)  # a template Glyphh no longer ships: the bot keeps what it installed
    assert (await bot_of(served, ana, SLUG))["plugins"] == [other, THEIRS, NOTES]
    res = await update(served, ana, SLUG, SLUG)
    assert res.status_code == 404 and res.json()["error"]["plugin"] == SLUG


async def test_a_plugin_is_brought_to_the_newest_version_and_the_persons_changes_stay(
    served: Served, ana: Person, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = await connected(served, ana)
    bot = await installed(served, ana, SLUG)
    mine = bot["spec"] | {"gates": {"worth": bot["spec"]["gates"]["worth"] | {"question": "Worth MY time?"}}}
    changed = {"name": "Mail Cat", "instructions": "You are Mail Cat. My own words.", "permission_mode": "auto"}
    changed |= {"spec": mine, "schedule": {"every": "day", "at": "07:30"}, "task": "My own task.", "examples": ["Go"]}
    res = await served.http.patch(f"/v1/bots/{SLUG}", json=changed, headers=ana.headers)
    assert res.status_code == 200, res.text
    scoped = {"connections": [{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}]}
    assert (await served.http.put(f"/v1/bots/{SLUG}/connections", json=scoped, headers=ana.headers)).status_code == 200
    shelved(monkeypatch, newer())
    before = await bot_of(served, ana, SLUG)
    assert before["plugins"] == [THEIRS | {"latest": "1.1.0"}]
    res = await update(served, ana, SLUG, SLUG)  # the new version uses Slack, which is not connected yet
    err = res.json()["error"]
    assert res.status_code == 422 and (err["reason"], err["apps"]) == ("connections", ["slack"])
    assert err["message"] == "Connect slack first: the new version uses it."
    assert await bot_of(served, ana, SLUG) == before  # refused whole: nothing of it was updated
    slack = (await linked(served, ana, "slack"))["slack"]
    res = await update(served, ana, SLUG, SLUG)
    assert res.status_code == 200, res.text
    now = res.json()
    assert now["plugins"] == [THEIRS | {"version": "1.1.0", "latest": "1.1.0"}]
    gates = now["spec"]["gates"]
    assert sorted(gates) == ["urgent", "worth"] and gates["urgent"]["question"] == "Is it urgent?"
    assert gates["worth"] == mine["gates"]["worth"]  # the person's own wording of a decision it had
    assert now["spec"]["hosts"] == ["hn.algolia.com"] and now["spec"]["builtins"] == ["inbox_label"]
    assert [(c["connection_id"], c["tools"]) for c in now["connections"]] == [
        (gmail["id"], [DRAFT, "gmail-find-email", "gmail-send-email"]),  # added to; none taken away
        (slack["id"], [POST]),
    ]
    same = ("name", "slug", "instructions", "permission_mode", "schedule", "task", "examples", "model", "look")
    assert {k: now[k] for k in same} == {k: before[k] for k in same} and now["name"] == "Mail Cat"
    assert "bot-inbox-triage-gate-urgent" in now["gate_models"]
    async with engine.connect() as conn:
        rows = list(await conn.execute(select(BotPlugin).where(BotPlugin.bot_id == uuid.UUID(bot["id"]))))
    assert len(rows) == 1 and rows[0].files == newer().files and rows[0].version == "1.1.0"
    seen: dict[str, str] = {}

    async def go(turn: Turn) -> Ended:
        seen["digest"] = (turn.plugins[0] / "skills" / "digest" / "SKILL.md").read_text()
        return Ended(text="Done.", session=SESSION, input_tokens=1, output_tokens=1)

    any_component(served)
    served.agent.script = [go]
    run = await ran(served, ana, SLUG)
    turn = served.agent.turns[-1]
    assert run["status"] == "done" and seen["digest"] == NEW_SKILL
    assert turn.skills == ["inbox-triage:digest", "inbox-triage:urgent"] and turn.message == "My own task."
    assert {DRAFT.replace("-", "_"), POST.replace("-", "_"), "fetch", "inbox_label", "decide"} <= {
        t.name for t in turn.tools
    }
    assert "My own words." in turn.system and "rewritten" not in turn.system
    again = await update(served, ana, SLUG, SLUG)  # up to date already: nothing changes
    aside = {"updated_at": "", "last_run": None}
    assert again.status_code == 200 and again.json() | aside == now | aside


async def test_an_update_adds_to_the_bots_own_connection_of_an_app(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    await linked(served, ana, "gmail", "slack")
    second = (await linked(served, ana, "gmail", n=2))["gmail"]
    await installed(served, ana, SLUG)
    scoped = {"connections": [{"connection_id": second["id"], "tools": ["gmail-find-email"]}]}
    res = await served.http.put(f"/v1/bots/{SLUG}/connections", json=scoped, headers=ana.headers)
    assert res.status_code == 200, res.text
    shelved(monkeypatch, newer())
    now = (await update(served, ana, SLUG, SLUG)).json()
    assert [(c["app"], c["tools"]) for c in now["connections"]] == [
        ("gmail", [DRAFT, "gmail-find-email"]),
        ("slack", [POST]),
    ]
    assert now["connections"][0]["connection_id"] == second["id"]  # the account the person chose, not the first


async def test_a_plugin_that_is_not_there_is_not_found(served: Served, ana: Person) -> None:
    await connected(served, ana)
    await installed(served, ana, SLUG)
    own = await made_bot(served, ana, connections=[])
    res = await update(served, ana, SLUG, "nope")
    err = res.json()["error"]
    assert res.status_code == 404 and err["message"] == "The bot has no such plugin from a template."
    assert (err["slug"], err["plugin"]) == (SLUG, "nope")
    assert (await update(served, ana, own["slug"], "notes")).status_code == 404  # its own notes are the person's
    assert (await update(served, ana, own["slug"], SLUG)).status_code == 404  # another bot's plugin
    assert (await update(served, ana, "no-such-bot", SLUG)).status_code == 404
    assert (await served.http.post(f"/v1/bots/{SLUG}/plugins/{SLUG}/update")).status_code == 401
    res = await update(served, ana, SLUG, SLUG)  # the version it has is the newest
    assert res.status_code == 200 and res.json()["plugins"] == [THEIRS]
