"""The Agent SDK's turn (ops/bots/agent/sdk.py; docs/specs/bot-agent-loop.md, 3), with the CLI behind the SDK's client
faked (tests/bots/cli.py): the session is locked to the bot's own tools (no built-in tool, no setting or MCP server
of the machine, a hook refusing anything else, none of the server's settings in the CLI's environment), every tool
call goes through the permission callback to the turn's `call`, and the turn ends on the agent's words, a question
for the person, or a failure said plainly."""

from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import SystemMessage

from glyphh_server.ops.bots.agent import sdk
from glyphh_server.ops.bots.agent.tools import Tool
from glyphh_server.ops.bots.agent.turn import ASKED, ERROR, RESULT, Outcome, Turn
from tests.bots.cli import HANG, SESSION, cli, init, result, says, use
from tests.bots.conftest import Served, answered, connected, made_bot, ran
from tests.db.helpers import Person

CLAUDE_CODE: tuple[str, ...] = (
    "Bash", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep", "WebFetch", "WebSearch", "Task",
    "Agent", "TodoWrite",
)  # fmt: skip
FIND = Tool("find_mail", "gmail-find-email", "Find Email", "Find emails", {"type": "object", "properties": {}}, True)
SEND = Tool("send_mail", "gmail-send-email", "Send Email", "Send one", {"type": "object", "properties": {}}, False)
PERMITS: dict[str, Outcome | None] = {  # what the bot's permissions make of a call; None: it may make it
    "find_mail": None,
    "send_mail": Outcome(ASKED, {"question": "Send Email in Gmail?"}),
    "blocked": Outcome(ERROR, "Blocked is not allowed on the Gmail connection."),
    "broken": None,
    "words": None,
    "ask": None,
    "crashes": None,
}
OUTCOMES: dict[str, Outcome] = {
    "find_mail": Outcome(RESULT, [{"id": "m1"}]),
    "broken": Outcome(ERROR, "Find Email failed: the account's token was revoked"),
    "words": Outcome(RESULT, "plain words"),
    "ask": Outcome(ASKED, {"question": "Which channel?"}),
}


def a_turn(folder: Path, **over: Any) -> Turn:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def allowed(name: str, given: dict[str, Any]) -> Outcome | None:
        calls.append((name, given))
        return PERMITS[name]  # a name it does not know: the server's own failure

    async def made(name: str, given: dict[str, Any]) -> Outcome:
        return OUTCOMES[name]  # "crashes": the server's own failure while the call is made

    async def call(name: str, given: dict[str, Any]) -> Outcome:
        return await allowed(name, given) or await made(name, given)

    said: dict[str, Any] = {"system": "You are Inbox Cat.", "message": "Hi", "tools": [FIND, SEND], "call": call}
    said |= {"allowed": allowed, "made": made}
    made = Turn(**{**said, "model": "claude-haiku-5-5", "effort": None, "key": "sk-ant-run", "folder": folder,
                   "store": None, **over})  # fmt: skip
    made.calls = calls  # type: ignore[attr-defined]
    return made


def played(monkeypatch: pytest.MonkeyPatch, *script: Any, **more: Any) -> Any:
    made = cli(*script, **more)
    monkeypatch.setattr(sdk, "ClaudeSDKClient", made)
    return made


def test_the_options_lock_the_session_to_the_bots_own_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLYPHH_SECRET_KEY", "the-servers-own-signing-key")
    monkeypatch.setenv("GLYPHH_DATABASE_URL", "postgresql://the-servers-database")
    session = sdk.Session(a_turn(tmp_path))
    o = session.options()
    assert o.tools == [] and o.skills == [] and o.plugins == []  # no built-in tool exists
    assert o.strict_mcp_config is True and o.setting_sources == []  # nothing of the machine is read
    assert set(CLAUDE_CODE) <= set(o.disallowed_tools) and o.allowed_tools == []
    assert o.permission_mode == "default" and o.can_use_tool == session.can_use
    assert list(o.mcp_servers) == ["bot"] and o.mcp_servers["bot"]["type"] == "sdk"  # type: ignore[index, union-attr]
    assert [m.hooks for m in o.hooks["PreToolUse"]] == [[session.hook]] and list(o.hooks) == ["PreToolUse"]  # type: ignore[index, arg-type]
    assert o.system_prompt == "You are Inbox Cat." and o.cwd == str(tmp_path)
    assert (o.model, o.effort, o.max_turns, o.resume) == ("claude-haiku-5-5", None, 25, None)
    assert o.session_store is None and o.session_store_flush == "eager"
    assert {k: v for k, v in o.env.items() if k.startswith("GLYPHH_")} == {
        k: "" for k in sdk.os.environ if k.startswith("GLYPHH_")
    }
    assert o.env["GLYPHH_SECRET_KEY"] == "" and o.env["GLYPHH_DATABASE_URL"] == ""
    assert o.env["ANTHROPIC_API_KEY"] == "sk-ant-run" and o.env["CLAUDE_CONFIG_DIR"] == str(tmp_path / ".claude")
    assert o.env["DISABLE_TELEMETRY"] == "1" and o.env["DISABLE_AUTOUPDATER"] == "1"
    assert o.stderr is not None and o.stderr("a line of the CLI's") is None  # type: ignore[func-returns-value]


def test_a_bot_with_skills_gets_the_skill_tool_and_only_its_own_skills(tmp_path: Path) -> None:
    plugin = tmp_path / "plugins" / "notes"
    turn = a_turn(tmp_path, skills=["notes:replies"], plugins=[plugin], session=SESSION, effort="low", turns=3)
    o = sdk.Session(turn).options()
    assert o.tools == ["Skill"] and o.skills == ["notes:replies"]
    assert o.plugins == [{"type": "local", "path": str(plugin)}]
    assert (o.resume, o.effort, o.max_turns) == (SESSION, "low", 3)
    assert set(CLAUDE_CODE) <= set(o.disallowed_tools) and o.permission_mode == "default"


async def test_the_hook_refuses_any_tool_that_is_not_the_bots(tmp_path: Path) -> None:
    session = sdk.Session(a_turn(tmp_path))
    for name in ("Bash", "Read", "WebFetch", "mcp__github__create_issue", ""):
        refused = (await session.hook({"tool_name": name}, None, None))["hookSpecificOutput"]
        assert refused["permissionDecision"] == "deny" and refused["hookEventName"] == "PreToolUse", name
        assert refused["permissionDecisionReason"] == sdk.NOT_YOURS
    for name in ("mcp__bot__find_mail", "Skill"):
        assert await session.hook({"tool_name": name}, "toolu_1", None) == {}


async def test_a_turn_uses_the_bots_tools_and_ends_on_its_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = (init("mcp__bot__find_mail", "mcp__bot__send_mail"), says("Looking."), use("mcp__bot__find_mail", q="x"))
    other = SystemMessage("status", {"status": "compacting"})  # a message that is none of the turn's own
    made = played(monkeypatch, *script, other, says("One letter."), result("One letter: **Lunch**. "))
    turn = a_turn(tmp_path / "run")
    got = await sdk.run(turn)
    client = made.made[0]
    assert client.message == "Hi" and (tmp_path / "run").is_dir()
    assert turn.calls == [("find_mail", {"q": "x"})]  # type: ignore[attr-defined]
    assert client.used == [("result", '[{"id": "m1"}]')]  # the tool answered what the callback's call came to
    assert (got.text, got.error, got.asked, got.session) == ("One letter: **Lunch**.", "", False, SESSION)
    assert (got.input_tokens, got.output_tokens) == (123, 40)  # cache writes and reads are input
    assert got.tools == ["mcp__bot__find_mail", "mcp__bot__send_mail"]
    listed = await client.rpc("tools/list", {})
    assert [t["name"] for t in listed["tools"]] == ["find_mail", "send_mail"]
    assert listed["tools"][0]["description"] == "Find emails"


async def test_a_tool_that_must_ask_the_person_ends_the_turn_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = played(monkeypatch, says("Sending."), use("mcp__bot__send_mail", to="grace"), says("never"), result("never"))
    got = await sdk.run(a_turn(tmp_path, session="carried-on"))
    assert made.made[0].used == [("interrupt", sdk.WAITING)]
    assert (got.asked, got.text, got.error, got.session) == (True, "", "", SESSION)
    assert (got.input_tokens, got.output_tokens) == (123, 40)  # the go is metered all the same


async def test_a_tool_call_the_server_cannot_make_at_all_ends_the_turn_and_fails_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the desk itself raising (Ada unreachable, say) is not a denial the agent may carry on from
    made = played(monkeypatch, use("mcp__bot__unreachable"), says("never"), result("never"))
    got = await sdk.run(a_turn(tmp_path))
    assert made.made[0].used == [("interrupt", "The run failed: KeyError: 'unreachable'")]
    assert (got.asked, got.text, got.error) == (False, "", "The run failed: KeyError: 'unreachable'")
    assert got.input_tokens == 123


async def test_a_refused_call_is_told_to_the_agent_and_its_own_question_ends_the_turn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = played(monkeypatch, use("mcp__bot__blocked"), use("mcp__bot__ask"), use("mcp__bot__words"), result(None))
    turn = a_turn(tmp_path)
    turn.tools = [*turn.tools, *(Tool(n, n, n.title(), "", FIND.schema, True) for n in ("blocked", "ask", "words"))]
    got = await sdk.run(turn)
    assert made.made[0].used == [
        ("denied", "Blocked is not allowed on the Gmail connection."),
        ("result", sdk.WAITING),
        ("interrupt", sdk.WAITING),  # it waits on the person: nothing more runs in this go
    ]
    assert (got.asked, got.error) == (True, "")


async def test_a_call_the_server_fails_to_make_fails_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    made = played(monkeypatch, use("mcp__bot__crashes"), result("never"))
    turn = a_turn(tmp_path)
    turn.tools = [*turn.tools, Tool("crashes", "crashes", "Crashes", "", FIND.schema, True)]
    got = await sdk.run(turn)
    assert made.made[0].used == [("error", "The run failed: KeyError: 'crashes'")]
    assert (got.error, got.text, got.asked) == ("The run failed: KeyError: 'crashes'", "", False)


async def test_what_is_not_the_bots_is_refused_and_an_error_is_told_to_the_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uses = (use("Bash", command="env"), use("mcp__bot__broken"), use("mcp__bot__words"))
    made = played(monkeypatch, *uses, result(None))
    turn = a_turn(tmp_path)
    turn.tools = [*turn.tools, Tool("broken", "broken", "Broken", "", FIND.schema, True)]
    turn.tools.append(Tool("words", "words", "Words", "", FIND.schema, True))
    session = sdk.Session(turn)
    monkeypatch.setattr(sdk, "Session", lambda _: session)
    got = await sdk.run(turn)
    assert made.made[0].used == [
        ("hook", sdk.NOT_YOURS),
        ("error", "Find Email failed: the account's token was revoked"),
        ("result", "plain words"),
    ]
    assert turn.calls == [("broken", {}), ("words", {})] and got.text == ""  # type: ignore[attr-defined]
    denied = await session.can_use("Bash", {"command": "env"}, None)  # past the hook, the callback refuses it too
    assert (denied.behavior, denied.message, denied.interrupt) == ("deny", sdk.NOT_YOURS, False)
    unasked = await made.made[0].rpc("tools/call", {"name": "find_mail", "arguments": {"q": "never allowed"}})
    assert unasked["isError"] is True and unasked["content"][0]["text"] == sdk.NOT_YOURS  # no call without permission
    assert sdk.said("x" * (sdk.RESULT_MAX + 9)).endswith("\n[cut: the result was longer]")


async def test_a_turn_with_no_final_text_ends_on_the_agents_last_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    played(monkeypatch, says("First."), says("Two letters.", "Both from Grace."), says(), result(None, usage=None))
    got = await sdk.run(a_turn(tmp_path))
    assert got.text == "Two letters.\n\nBoth from Grace." and (got.input_tokens, got.output_tokens) == (0, 0)


@pytest.mark.parametrize(
    ("ending", "why"),
    [
        (result(None, "error_max_turns"), "It took more steps than a run may: ask for less at once."),
        (result(None, "error_max_budget_usd"), "It reached the most a run may spend."),
        (result(None, "error_during_execution", errors=["overloaded", "gave up"]), "overloaded; gave up"),
        (result("Invalid API key", is_error=True), "Invalid API key"),
        (result(None, "error_during_execution"), "error_during_execution"),
    ],
)
async def test_a_turn_that_fails_says_why(
    ending: Any, why: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    played(monkeypatch, says("Working."), ending)
    got = await sdk.run(a_turn(tmp_path))
    assert (got.error, got.text, got.asked) == (why, "", False) and got.input_tokens == 123


async def test_a_turn_with_no_result_or_a_cli_that_cannot_start_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    played(monkeypatch, says("Working."))
    got = await sdk.run(a_turn(tmp_path, session="s-1"))
    assert (got.error, got.session) == ("Claude ended the turn without a result.", "s-1")
    played(monkeypatch, starts=False)
    got = await sdk.run(a_turn(tmp_path, session="s-1"))
    assert (got.error, got.session, got.asked) == ("Claude could not run: the CLI is not there", "s-1", False)


async def test_a_turn_out_of_time_is_interrupted_and_fails_with_what_it_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = played(monkeypatch, says("Working."), HANG, after=(result("cut off"),))
    got = await sdk.run(a_turn(tmp_path, seconds=0.05))
    assert made.made[0].interrupted
    assert (got.error, got.text) == ("It ran out of time (0.05 seconds).", "")
    assert (got.input_tokens, got.output_tokens, got.session) == (123, 40, SESSION)
    monkeypatch.setattr(sdk, "LATE_SECONDS", 0.05)  # a CLI that does not answer the interrupt either
    played(monkeypatch, HANG, after=(HANG,))
    got = await sdk.run(a_turn(tmp_path, seconds=0.05, session="s-1"))
    assert (got.error, got.input_tokens, got.session) == ("It ran out of time (0.05 seconds).", 0, "s-1")


REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
SEND_MAIL: str = "mcp__bot__gmail_send_email"
LINE: dict[str, Any] = {"type": "user", "uuid": "u-1", "message": {"role": "user", "content": "Reply to Grace"}}


async def test_a_cloud_bots_real_turn_is_locked_down_and_carried_on_from_its_kept_session(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole server with the real sdk.run and only the CLI faked: the options built for a bot on Glyphh cloud."""
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    served.app.state.bots.agent = sdk.run
    seen: dict[str, Any] = {}

    async def looked(client: Any) -> None:
        o = client.options
        seen["skill"] = (Path(o.plugins[0]["path"]) / "skills" / "replies" / "SKILL.md").read_text()
        seen["loaded"] = await o.session_store.load({"project_key": Path(o.cwd).name, "session_id": SESSION})
        await o.session_store.append({"project_key": Path(o.cwd).name, "session_id": SESSION}, [LINE])

    first = played(monkeypatch, init(SEND_MAIL, "mcp__bot__decide", "Skill"), looked, use(SEND_MAIL, **REPLY))
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    assert run["status"] == "needs_input" and run["question"]["question"] == "Send Email in Gmail?"
    o = first.made[0].options
    assert first.made[0].message == "Reply to Grace" and "You are Inbox Cat" in o.system_prompt
    assert o.tools == ["Skill"] and o.skills == ["notes:replies"] and "One paragraph" in seen["skill"]
    assert o.strict_mcp_config is True and o.setting_sources == [] and o.permission_mode == "default"
    assert set(CLAUDE_CODE) <= set(o.disallowed_tools) and list(o.mcp_servers) == ["bot"]
    assert o.can_use_tool is not None and list(o.hooks) == ["PreToolUse"]
    folder = Path(o.cwd)
    assert folder.name == run["id"] and not folder.exists()  # the run's own folder, gone once the go is over
    assert (
        o.env["CLAUDE_CONFIG_DIR"] == str(folder / ".claude") and o.env["ANTHROPIC_API_KEY"] == "sk-ant-glyphh-test-key"
    )
    blanked = {k: v for k, v in o.env.items() if k.startswith("GLYPHH_")}
    assert set(blanked.values()) == {""} and {"GLYPHH_DATABASE_URL", "GLYPHH_SECRET_KEY"} <= set(blanked)
    assert (o.resume, seen["loaded"], o.max_turns) == (None, None, 25)
    assert first.made[0].used == [("interrupt", sdk.WAITING)] and served.pd.runs == []
    assert (run["input_tokens"], run["output_tokens"]) == (123, 40)

    second = played(monkeypatch, looked, use(SEND_MAIL, **REPLY), result("Sent it."))
    done = await answered(served, ana, run["id"], "yes")
    assert (done["status"], done["output"]) == ("done", "Sent it.") and len(served.pd.runs) == 1
    again = second.made[0]
    assert again.options.resume == SESSION and seen["loaded"] == [LINE]  # carried on from its own conversation
    assert "said yes" in again.message and again.used[0][0] == "result" and '"msg_1"' in again.used[0][1]
    assert await again.options.session_store.load({"session_id": SESSION}) is None  # gone with the run's end
    assert (done["input_tokens"], done["output_tokens"]) == (246, 80)


async def test_a_cloud_bot_with_no_notes_has_no_tool_but_its_own(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = await made_bot(served, ana, skills={})
    served.app.state.bots.agent = sdk.run
    made = played(
        monkeypatch, use("Bash", command="cat /etc/passwd"), use("Read", file_path="/app/.env"), result("No.")
    )
    run = await ran(served, ana, bot["slug"], "Read /etc/passwd")
    o = made.made[0].options
    assert (o.tools, o.skills, o.plugins) == ([], [], []) and run["output"] == "No."
    assert made.made[0].used == [("hook", sdk.NOT_YOURS), ("hook", sdk.NOT_YOURS)] and run["steps"] == []
    listed = await made.made[0].rpc("tools/list", {})
    assert sorted(t["name"] for t in listed["tools"]) == [
        "ask_person",
        "decide",
        "gmail_find_email",
        "gmail_send_email",
    ]
