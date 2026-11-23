"""The Claude Agent SDK, one turn (docs/specs/bot-agent-loop.md, 2, 3, 6.1): the bot's tools as one in-process MCP
server and nothing else. No built-in tool exists in the session (no shell, no files, no web), no setting, MCP server
or plugin of the machine is read, a hook refuses any tool that is not the bot's, and the CLI's process is given none
of the server's own settings. Every tool call goes through the permission callback, which holds the bot's permissions
and nothing else (`Turn.allowed`: its mode and each connection's allow / ask / deny): an action the person must
approve is denied and the turn ends. An allowed call is made by the tool's handler (`Turn.made`); `ask_person` ends
the turn the same way. The run then waits, and an answer resumes the session from the run's store."""

import asyncio
import json
import os
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SdkMcpTool,
    SystemMessage,
    TextBlock,
    create_sdk_mcp_server,
)

from glyphh_server.ops.bots.agent.turn import ASKED, ERROR, RESULT, Ended, Outcome, Turn, ended

SERVER: str = "bot"
PREFIX: str = f"mcp__{SERVER}__"
SKILL: str = "Skill"
# Claude Code's own tools: none exists in a bot's session (tools=[]), and each is refused by name as well
BUILT_INS: tuple[str, ...] = (
    *("Bash", "BashOutput", "KillShell", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit", "Glob", "Grep"),
    *("WebFetch", "WebSearch", "Task", "Agent", "TodoWrite", "ExitPlanMode", "ListMcpResources", "ReadMcpResource"),
)
WAITING: str = "The person is being asked. Stop here: you will be told their answer."
NOT_YOURS: str = "That tool is not one of this bot's."
RESULT_MAX: int = 200_000
LATE_SECONDS: float = 10.0
QUIET: dict[str, str] = dict.fromkeys(
    ("DISABLE_TELEMETRY", "DISABLE_AUTOUPDATER", "DISABLE_ERROR_REPORTING", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"),
    "1",
)


def env(turn: Turn) -> dict[str, str]:
    """The CLI's environment: the key the run is billed on, its config in the run's own folder, and every setting of
    the server's own (GLYPHH_*: the database, the signing keys) blanked."""
    blank = {k: "" for k in os.environ if k.startswith("GLYPHH_")}
    return {**blank, **QUIET, "ANTHROPIC_API_KEY": turn.key, "CLAUDE_CONFIG_DIR": str(turn.folder / ".claude")}


def said(value: Any) -> str:
    """A tool's result as the agent reads it."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= RESULT_MAX else text[:RESULT_MAX] + "\n[cut: the result was longer]"


class Session:
    """One turn's tools and its two walls: the permission callback (the bot's permissions, nothing else) and the
    hook."""

    def __init__(self, turn: Turn) -> None:
        self.turn = turn
        self.asked = False
        self.broke = ""  # why a tool call could not be made at all: it ends the turn, and fails the run
        self.listed: list[str] = []  # the session's own list of its tools, as its init says
        self.held: list[str] = []  # the calls the callback allowed and no handler has made yet

    @staticmethod
    def _key(name: str, given: dict[str, Any]) -> str:
        return name + json.dumps(given, sort_keys=True, default=str)

    def _broken(self, err: Exception) -> str:
        self.broke = f"The run failed: {type(err).__name__}: {err}"
        return self.broke

    async def can_use(self, name: str, given: dict[str, Any], context: Any) -> Any:
        if not name.startswith(PREFIX):
            return PermissionResultDeny(message=NOT_YOURS)
        if self.asked:  # the run waits on the person: nothing more runs in this go
            return PermissionResultDeny(message=WAITING, interrupt=True)
        try:
            got = await self.turn.allowed(name.removeprefix(PREFIX), given)
        except Exception as err:  # noqa: BLE001  the server's own failure (its database, say): the run fails
            return PermissionResultDeny(message=self._broken(err), interrupt=True)
        if got is None:
            self.held.append(self._key(name, given))
            return PermissionResultAllow(updated_input=given)
        if got.kind == ASKED:
            self.asked = True
            return PermissionResultDeny(message=WAITING, interrupt=True)
        return PermissionResultDeny(message=str(got.value))

    async def hook(self, given: Any, tool_use_id: str | None, context: Any) -> dict[str, Any]:
        name = str(given.get("tool_name") or "")
        if name.startswith(PREFIX) or name == SKILL:
            return {}
        refused = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": NOT_YOURS}
        return {"hookSpecificOutput": refused}

    def _handler(self, name: str) -> Any:
        async def handle(given: dict[str, Any]) -> dict[str, Any]:
            key = self._key(PREFIX + name, given)
            if key not in self.held:  # never a call the callback did not allow
                return {"content": [{"type": "text", "text": NOT_YOURS}], "is_error": True}
            self.held.remove(key)
            try:
                got = await self.turn.made(name, given)
            except Exception as err:  # noqa: BLE001  the server's own failure (Ada unreachable, say): the run fails
                got = Outcome(ERROR, self._broken(err))
            if got.kind == ASKED:
                self.asked = True
                got = Outcome(RESULT, WAITING)
            return {"content": [{"type": "text", "text": said(got.value)}], "is_error": got.kind == ERROR}

        return handle

    def options(self) -> ClaudeAgentOptions:
        tools = [SdkMcpTool(t.name, t.description, t.schema, self._handler(t.name)) for t in self.turn.tools]
        t = self.turn
        return ClaudeAgentOptions(
            system_prompt=t.system,
            tools=[SKILL] if t.skills else [],
            mcp_servers={SERVER: create_sdk_mcp_server(SERVER, tools=tools)},
            strict_mcp_config=True,
            setting_sources=[],
            disallowed_tools=list(BUILT_INS),
            permission_mode="default",
            can_use_tool=self.can_use,
            hooks={"PreToolUse": [HookMatcher(hooks=[self.hook])]},
            cwd=str(t.folder),
            model=t.model,
            effort=t.effort,  # type: ignore[arg-type]
            max_turns=t.turns,
            resume=t.session or None,
            session_store=t.store,
            session_store_flush="eager",
            skills=list(t.skills),
            plugins=[{"type": "local", "path": str(p)} for p in t.plugins],
            env=env(t),
            stderr=lambda line: None,
        )


async def _heard(client: Any, session: Session, turn: Turn) -> Ended:
    words: list[str] = []
    async for message in client.receive_response():
        if isinstance(message, SystemMessage) and message.subtype == "init":
            session.listed = [str(t) for t in message.data.get("tools") or []]
        elif isinstance(message, AssistantMessage):
            words = [b.text for b in message.content if isinstance(b, TextBlock)] or words
        elif isinstance(message, ResultMessage):
            got = ended(message, words, session.asked, turn.session)
            got.tools = session.listed
            if session.broke:
                got.asked, got.text, got.error = False, "", session.broke
            return got
    return Ended(session=turn.session, asked=session.asked, error="Claude ended the turn without a result.")


async def _late(client: Any, session: Session, turn: Turn) -> Ended:
    """A turn out of time: interrupted, its result (the tokens it used) waited for a moment, and failed saying so."""
    await client.interrupt()
    try:
        async with asyncio.timeout(LATE_SECONDS):
            got = await _heard(client, session, turn)
    except TimeoutError:
        got = Ended(session=turn.session)
    got.text, got.error = "", f"It ran out of time ({turn.seconds:g} seconds)."
    return got


async def run(turn: Turn) -> Ended:
    """The turn, from the person's message to the agent's last words, a question for the person, or a failure."""
    session = Session(turn)
    turn.folder.mkdir(parents=True, exist_ok=True)
    try:
        async with ClaudeSDKClient(session.options()) as client:
            await client.query(turn.message)
            try:
                async with asyncio.timeout(turn.seconds):
                    return await _heard(client, session, turn)
            except TimeoutError:
                return await _late(client, session, turn)
    except Exception as err:  # noqa: BLE001  the CLI could not start or died: the run fails saying so
        return Ended(session=turn.session, asked=session.asked, error=f"Claude could not run: {err}")
