"""The parts of a bot's agent turn, each on its own (ops/bots/agent): which calls ask (the permission table), the
tools a bot has and how each is described, what the agent is told, its know-how written as plugins, its session kept
in Postgres, and its limits."""

import json
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotPlugin
from glyphh_server.ops.bots.agent import permit, plugins, prompt, session, tools
from glyphh_server.ops.bots.agent import run as agent_run
from glyphh_server.ops.bots.agent.turn import Turn
from tests.bots.agents import play
from tests.bots.conftest import Served, connected, inbox, made_bot, ran
from tests.bots.fakes import SEND
from tests.db.helpers import Person

RUN, ASK, DENY = permit.RUN, permit.ASK, permit.DENY
TABLE: list[tuple[str, bool, str | None, str]] = [
    # Ask me first: an action asks unless its connection allows it; a read-only tool runs unless it says ask
    ("ask", False, None, ASK), ("ask", False, "ask", ASK), ("ask", False, "allow", RUN), ("ask", False, "deny", DENY),
    ("ask", True, None, RUN), ("ask", True, "ask", ASK), ("ask", True, "allow", RUN), ("ask", True, "deny", DENY),
    # Follow each app's settings: the connection's say; an action never set asks, a read-only one runs
    ("connection", False, None, ASK), ("connection", False, "ask", ASK), ("connection", False, "allow", RUN),
    ("connection", False, "deny", DENY), ("connection", True, None, RUN), ("connection", True, "ask", ASK),
    ("connection", True, "allow", RUN), ("connection", True, "deny", DENY),
    # Act on its own: nothing asks, and a denied tool is still refused
    ("auto", False, None, RUN), ("auto", False, "ask", RUN), ("auto", False, "allow", RUN),
    ("auto", False, "deny", DENY), ("auto", True, None, RUN), ("auto", True, "ask", RUN), ("auto", True, "allow", RUN),
    ("auto", True, "deny", DENY),
]  # fmt: skip


def a_tool(read_only: bool = False, permission: str | None = None, app: str = "Gmail") -> tools.Tool:
    return tools.Tool("gmail_send_email", "gmail-send-email", "Send Email", "Send one", {}, read_only, app, permission)


@pytest.mark.parametrize(("mode", "read_only", "permission", "verdict"), TABLE)
def test_the_mode_the_tool_and_its_connection_say_whether_a_call_asks(
    mode: str, read_only: bool, permission: str | None, verdict: str
) -> None:
    assert permit.verdict(mode, a_tool(read_only, permission)) == verdict


def test_an_approval_names_the_very_call_and_only_a_yes_to_it_is_kept() -> None:
    given = {"to": ["grace@navy.test", "ada@navy.test"], "subject": "Lunch", "body": "", "cc": None, "more": {"a": 1}}
    asked = permit.question(a_tool(), given)
    assert (asked["question"], asked["options"], asked["approval"]) == ("Send Email in Gmail?", ["yes", "no"], True)
    assert (asked["tool"], asked["step"]) == ("gmail-send-email", "gmail-send-email")
    assert asked["detail"] == 'to: grace@navy.test, ada@navy.test\nsubject: Lunch\nmore: {"a": 1}'
    assert asked["digest"] == permit.digest(dict(reversed(given.items()))) != permit.digest({**given, "subject": "x"})
    assert permit.question(a_tool(app=""), {})["question"] == "Send Email?"
    long = permit.detail({"body": "x" * 2_000})
    assert len(long) == permit.DETAIL_MAX and long.endswith("…")
    who = uuid.uuid4()
    kept = permit.granted(asked, "yes", who, "2026-11-22T10:00:00+00:00")
    assert kept == {"gmail-send-email": {"digest": asked["digest"], "by": str(who), "at": "2026-11-22T10:00:00+00:00"}}
    assert permit.granted(asked, "yes", None, "now")["gmail-send-email"]["by"] is None
    assert permit.granted(asked, "no", who, "now") == {}
    assert permit.granted({**asked, "approval": False}, "yes", who, "now") == {}  # not an approval
    assert permit.granted({"approval": True}, "yes", who, "now") == {}  # of no tool


def test_a_tool_is_named_for_the_agent_and_read_only_by_its_component_or_its_verb() -> None:
    assert tools.named("gmail-Send-email") == "gmail_send_email" and tools.named("a.b c") == "a_b_c"
    assert tools.reads("gmail-find-email", {}) and tools.reads("github-search-issues", {"annotations": None})
    assert not tools.reads("gmail-send-email", {}) and not tools.reads("fetch", {})  # no verb: not read-only
    assert not tools.reads("gmail-find-email", {"annotations": {"readOnlyHint": False}})  # its own say wins
    assert tools.reads("gmail-send-email", {"annotations": {"readOnlyHint": True}})
    assert not tools.reads("gmail-send-email", {"annotations": {"readOnlyHint": "yes"}})


def test_a_components_props_are_the_tools_json_schema_without_its_account() -> None:
    made = tools.schema(SEND["configurable_props"])
    assert made["required"] == ["to", "subject"] and list(made["properties"]) == ["to", "subject", "body", "format"]
    assert made["properties"]["to"] == {"type": "array", "items": {"type": "string"}, "description": "To"}
    assert made["properties"]["format"] == {"type": "string", "enum": ["text", "html"]}
    odd = [
        {"name": "secret", "type": "string", "hidden": True},
        {"name": "when", "type": "$.interface.timer", "label": "When", "description": "d" * 700},
        {"name": "size", "type": "integer", "options": [1, 2], "optional": True},
        {"name": "kind", "type": "string", "options": [{"label": "A", "value": "a"}, "b"]},
        {"name": "none", "type": "string", "options": []},
    ]
    props = tools.schema(odd)["properties"]
    assert list(props) == ["when", "size", "kind", "none"]
    assert props["when"]["type"] == "string" and len(props["when"]["description"]) == 600  # an unknown type is text
    assert props["size"] == {"type": "integer"} and props["kind"]["enum"] == ["a", "b"] and "enum" not in props["none"]


async def test_a_bot_has_its_connections_tools_fetch_its_built_ins_and_decide(served: Served, ana: Person) -> None:
    spec = inbox(hosts=["api.example.com"], builtins=["inbox_applications", "inbox_label", "no_such_tool"])
    gmail = await connected(served, ana, allow=False)
    scopes = [{"connection_id": gmail["id"], "tools": ["gmail-find-email", "gmail-send-email"]}]
    bot = await made_bot(served, ana, spec=spec, connections=scopes)
    await ran(served, ana, bot["slug"], "Hi")
    turn: Turn = served.agent.turns[0]
    found = {t.name: t for t in turn.tools}
    assert list(found) == [
        "gmail_find_email",
        "gmail_send_email",
        "fetch",
        "inbox_applications",
        "inbox_label",
        "decide",
        "ask_person",
    ]
    find, send = found["gmail_find_email"], found["gmail_send_email"]
    assert (find.key, find.title, find.app, find.read_only, find.permission) == (
        "gmail-find-email", "Find Email", "Gmail", True, None,
    )  # fmt: skip
    assert (send.read_only, send.description) == (False, "Send an email from your Gmail account")
    assert "gmail" not in send.schema["properties"] and find.schema["properties"] == {"q": {"type": "string"}}
    assert found["fetch"].read_only and "api.example.com" in found["fetch"].description
    assert found["inbox_applications"].read_only and not found["inbox_label"].read_only
    decide = found["decide"]
    assert decide.schema["properties"]["decision"]["enum"] == ["worth"] and decide.call is None
    assert "worth: Worth answering? (answer, skip)" in decide.description
    ask = found["ask_person"]
    assert ask.schema["properties"]["decision"]["enum"] == ["worth"] and ask.read_only and ask.call is None
    assert (
        "# Ada\n" in turn.system
        and "Use them as your instructions say." in turn.system
        and "- `worth`: Worth answering? One of: answer, skip." in turn.system
    )
    assert "# Know-how\nBefore that kind of work, load its skill: replies." in turn.system
    assert turn.system.startswith("You are Inbox Cat, a bot that works for the person talking to you. Answers the mail")


async def test_a_bot_with_nothing_is_told_it_has_no_tools_and_a_connection_gone_leaves_none(
    served: Served, ana: Person
) -> None:
    plain = await made_bot(served, ana, name="Plain", summary="", spec={}, skills={}, connections=[], task="")
    await ran(served, ana, plain["slug"])
    turn = served.agent.turns[0]
    assert [t.name for t in turn.tools] == ["ask_person"] and turn.skills == [] and turn.message == prompt.STANDING
    assert "decision" not in turn.tools[0].schema["properties"]  # it has no decisions to ask about
    assert turn.system.startswith("You are Plain, a bot that works for the person talking to you. Today is ")
    assert "You have no tools" in turn.system and "# Ada" not in turn.system and "Know-how" not in turn.system
    gmail = await connected(served, ana)
    scopes = [{"connection_id": gmail["id"], "tools": ["gmail-find-email"]}]
    bot = await made_bot(served, ana, spec={}, connections=scopes)
    served.pd.accounts = []  # the account is gone at Pipedream, and so the connection here
    assert (await served.http.post("/v1/connections/sync", headers=ana.headers)).status_code == 200
    gone = bot["connections"][0]["connection_id"]
    assert (await served.http.delete(f"/v1/connections/{gone}", headers=ana.headers)).status_code in (204, 404)
    await ran(served, ana, bot["slug"], "Anything new?")
    assert [t.name for t in served.agent.turns[1].tools] == ["ask_person"]


def test_what_a_waiting_run_is_carried_on_with() -> None:
    assert prompt.approved({}, "yes") == prompt.YES and prompt.approved({}, "no") == prompt.NO
    entries = [
        {"label": "Lunch", "key": "m1", "outcome": "answer", "by": "person"},
        {"label": "Spam", "key": "m2", "outcome": "skip", "by": "ada"},
    ]
    said = prompt.decided("worth", entries)
    assert said == "The person answered (worth): Lunch (id m1): answer. Carry on with these."
    assert prompt.heard("#team") == "The person answered: #team. Carry on."
    bot = SimpleNamespace(task="  Sweep the inbox. ")
    assert prompt.task(bot, " now ") == "now" and prompt.task(bot, " ") == "Sweep the inbox."
    gateless = SimpleNamespace(name="B", summary="", instructions="", spec={"gates": {"worth": {}}})
    assert "# Ada" not in prompt.system(gateless, {}, [])  # decide is not among its tools


SIDE: dict[str, Any] = {"code": [{"skill": "parse", "scripts": ["skills/parse/scripts/read.py"], "why": "PDFs"}]}
FILES: dict[str, str] = {
    plugins.MANIFEST: json.dumps({"name": "screener", "version": "1.2.0"}),
    plugins.SIDECAR: json.dumps(SIDE),
    "skills/parse/SKILL.md": "---\nname: parse\n---\nRead the resume.",
    "skills/parse/scripts/read.py": "print('read')",
    "skills/Not A Skill/SKILL.md": "no",
    "../outside.txt": "never written",
    "/etc/absolute": "never written",
    "": "never written",
}


def test_a_plugin_names_its_skills_and_code_and_is_written_inside_its_own_folder(tmp_path: Path) -> None:
    made = plugins.Plugin("screener", "1.2.0", "template:resume-screener", FILES)
    assert made.skills == ["screener:parse"]
    assert made.code == [{"skill": "parse", "scripts": ["skills/parse/scripts/read.py"]}]
    assert made.scripts == ["skills/parse/scripts/read.py"]
    bare = plugins.Plugin("bare", "1.0.0", "personal", {plugins.SIDECAR: "{}"})
    assert (bare.skills, bare.code, bare.scripts) == ([], [], [])
    assert plugins.Plugin("none", "1.0.0", "personal", {}).code == []
    (root, other) = plugins.written(tmp_path, [made, bare])
    assert root == tmp_path / "plugins" / "screener" and other == tmp_path / "plugins" / "bare"
    assert (root / "skills" / "parse" / "scripts" / "read.py").read_text() == "print('read')"
    assert json.loads((root / plugins.MANIFEST).read_text())["version"] == "1.2.0"
    written = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file())
    assert not any("outside" in p or "absolute" in p for p in written) and len(written) == 6
    assert not (tmp_path.parent / "outside.txt").exists() and not (tmp_path / "plugins" / "outside.txt").exists()
    assert plugins.notes(SimpleNamespace(skills={}, name="B")) is None
    own = plugins.notes(SimpleNamespace(skills={"replies": "Short."}, name="Inbox Cat"))
    assert own is not None and own.skills == ["notes:replies"] and own.source == "personal"
    assert json.loads(own.files[plugins.MANIFEST])["description"] == "Inbox Cat's own notes"


async def test_a_run_is_given_the_bots_installed_plugins_then_its_own_notes(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    bot = await made_bot(served, ana)
    row = {"org_id": ana.org_id, "bot_id": uuid.UUID(bot["id"]), "name": "screener", "version": "1.2.0"}
    async with engine.begin() as conn:
        await conn.execute(insert(BotPlugin).values(**row, source="template:resume-screener", files=FILES))
    seen: dict[str, Any] = {}

    async def go(turn: Turn) -> Any:
        seen["plugins"] = [str(p.relative_to(turn.folder)) for p in turn.plugins]
        seen["skill"] = (turn.plugins[0] / "skills" / "parse" / "SKILL.md").read_text()
        seen["notes"] = (turn.plugins[1] / "skills" / "replies" / "SKILL.md").read_text()
        return await play(text="Read.")(turn)

    served.agent.script = [go]
    run = await ran(served, ana, bot["slug"], "Hi")
    turn = served.agent.turns[0]
    assert run["output"] == "Read." and turn.skills == ["screener:parse", "notes:replies"]
    assert seen["plugins"] == ["plugins/screener", "plugins/notes"] and "Read the resume." in seen["skill"]
    assert "One paragraph, no sign-off." in seen["notes"]
    assert turn.folder == agent_run.FOLDERS / run["id"] and not turn.folder.exists()  # removed after the go
    assert "load its skill: parse, replies." in turn.system


async def test_a_runs_session_is_kept_in_postgres_in_order_and_dropped(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    bot = await made_bot(served, ana)
    run = await ran(served, ana, bot["slug"], "Hi")
    other = await made_bot(served, ana, name="Other Cat", connections=[])
    another = await ran(served, ana, other["slug"], "Hi")
    store = session.Sessions(engine, ana.org_id, uuid.UUID(run["id"]))
    theirs = session.Sessions(engine, ana.org_id, uuid.UUID(another["id"]))
    key = {"project_key": "the-runs-folder", "session_id": "s-1"}
    assert await store.load(key) is None
    await store.append(key, [])  # nothing to write
    assert await store.load(key) is None
    lines = [{"type": "user", "uuid": f"u-{n}", "message": {"content": f"line {n}"}} for n in range(5)]
    await store.append(key, lines[:2])
    await store.append({**key, "subpath": "subagents/agent-1"}, [{"type": "user", "uuid": "sub"}])
    await store.append({"session_id": "s-2"}, [{"type": "user", "uuid": "other session"}])
    await theirs.append(key, [{"type": "user", "uuid": "another run"}])
    await store.append({**key, "project_key": "a-new-machines-folder"}, lines[2:])  # the folder's name is not kept
    assert await store.load(key) == lines  # in the order written, this session's own lines only
    assert await store.load({**key, "subpath": "subagents/agent-1"}) == [{"type": "user", "uuid": "sub"}]
    assert await store.load({**key, "subpath": None}) == lines
    await session.drop(engine, ana.org_id, uuid.UUID(run["id"]))
    assert await store.load(key) is None and await store.load({"session_id": "s-2"}) is None
    assert await theirs.load(key) == [{"type": "user", "uuid": "another run"}]


async def test_a_bot_whose_notes_or_decisions_the_runner_cannot_hold_is_refused_saying_why(
    served: Served, ana: Person
) -> None:
    body = {"name": "Inbox Cat", "instructions": "Sort the mail.", "spec": inbox(), "skills": {"Bad Name": "x"}}
    res = await served.http.post("/v1/bots", json=body, headers=ana.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "skills"
    assert "lower case letters, digits and -: 'Bad Name' is not" in res.json()["error"]["message"]
    no_outcomes = {"worth": {**inbox()["gates"]["worth"], "outcomes": []}}
    res = await served.http.post(
        "/v1/bots", json={**body, "skills": {}, "spec": {"gates": no_outcomes}}, headers=ana.headers
    )
    said = res.json()["error"]
    assert res.status_code == 422 and said["reason"] == "spec" and said["message"].startswith("The bot is not right: ")
    assert said["problems"] and said["problems"][0] in said["message"]
    made = await made_bot(served, ana, connections=[])  # one that fits: an Ada model a decision, and its memory
    assert made["gate_models"][0] == "bot-inbox-cat-gate-worth" and len(made["gate_models"]) > 1
    plain = await made_bot(served, ana, name="Plain", spec={}, connections=[])
    assert plain["gate_models"] and all("-gate-" not in m for m in plain["gate_models"])  # its memory alone


def test_a_bots_limits_are_its_own_where_it_sets_one_else_the_defaults() -> None:
    assert agent_run.limits(SimpleNamespace(spec={})) == {
        "turns": 25, "seconds": 300, "tokens": 400_000, "runs_per_day": 200,
    }  # fmt: skip
    own = {"turns": 3, "seconds": 0, "tokens": "many", "runs_per_day": -1, "other": 9}
    assert agent_run.limits(SimpleNamespace(spec={"limits": own})) == {
        "turns": 3, "seconds": 300, "tokens": 400_000, "runs_per_day": 200,
    }  # fmt: skip
    assert agent_run.limits(SimpleNamespace(spec={"limits": [1]}))["turns"] == 25
