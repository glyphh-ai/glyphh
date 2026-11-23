"""The Claude Code CLI behind the Agent SDK's client, faked at the SDK's own boundary (`ClaudeSDKClient`, as
ops/bots/agent/sdk.py uses it): a test scripts what the CLI does in a turn. A tool use goes the way the real CLI
sends it: the PreToolUse hook first, then the permission callback (`options.can_use_tool`), then the tool itself,
called over JSON-RPC at the options' in-process MCP server through the SDK's own bridge. Every message it yields is
the SDK's own type."""

import asyncio
from typing import Any, ClassVar

from claude_agent_sdk import AssistantMessage, PermissionResultDeny, ResultMessage, SystemMessage, TextBlock
from claude_agent_sdk._internal.sdk_mcp_bridge import SdkMcpBridge

SESSION: str = "0a0a0a0a-1111-2222-3333-444444444444"
USAGE: dict[str, int] = {
    "input_tokens": 100, "cache_creation_input_tokens": 20, "cache_read_input_tokens": 3, "output_tokens": 40,
}  # fmt: skip
HELLO: dict[str, Any] = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "c", "version": "1"},
}


def init(*tools: str) -> SystemMessage:
    return SystemMessage("init", {"tools": list(tools), "session_id": SESSION})


def says(*texts: str) -> AssistantMessage:
    return AssistantMessage([TextBlock(t) for t in texts], "claude-test")


def result(text: str | None = "Done.", subtype: str = "success", **more: Any) -> ResultMessage:
    said: dict[str, Any] = {"is_error": subtype != "success", "session_id": SESSION, "usage": dict(USAGE), **more}
    return ResultMessage(subtype=subtype, duration_ms=1, duration_api_ms=1, num_turns=1, result=text, **said)


def use(name: str, **given: Any) -> tuple[str, str, dict[str, Any]]:
    return ("use", name, given)


HANG: tuple[str] = ("hang",)


class Cli:
    """One client. `script`: what the turn does, in order: an SDK message to yield, `use(tool, ...)`, HANG (it never
    answers), or a function awaited with the client; `after`: what it yields once interrupted. `used`: what each
    tool use came to."""

    script: ClassVar[list[Any]] = []
    after: ClassVar[list[Any]] = []
    starts: ClassVar[bool] = True
    made: ClassVar[list["Cli"]] = []  # every client made of this script, in order

    def __init__(self, options: Any) -> None:
        self.options, self.message, self.interrupted = options, "", False
        self.used: list[tuple[str, Any]] = []
        self.bridge: SdkMcpBridge | None = None
        self.ids = 0
        type(self).made.append(self)

    async def __aenter__(self) -> "Cli":
        if not self.starts:
            raise RuntimeError("the CLI is not there")
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self.bridge is not None:
            await self.bridge.aclose()
            self.bridge = None

    async def query(self, message: str) -> None:
        self.message = message

    async def interrupt(self) -> None:
        self.interrupted = True

    async def rpc(self, method: str, params: dict[str, Any]) -> Any:
        """A request to the bot's MCP server, as the CLI sends it; its result."""
        if self.bridge is None:
            self.bridge = SdkMcpBridge("bot", self.options.mcp_servers["bot"]["instance"])
            await self.bridge.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": HELLO})
            await self.bridge.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.ids += 1
        got = await self.bridge.handle({"jsonrpc": "2.0", "id": self.ids, "method": method, "params": params})
        assert got is not None and "result" in got, got
        return got["result"]

    async def _use(self, name: str, given: dict[str, Any]) -> bool:
        """A tool use; False when it ended the turn (the person is being asked)."""
        hook = self.options.hooks["PreToolUse"][0].hooks[0]
        refused = (await hook({"tool_name": name, "tool_input": given}, "toolu_1", None)).get("hookSpecificOutput")
        if refused:
            self.used.append(("hook", refused["permissionDecisionReason"]))
            return True
        allowed = await self.options.can_use_tool(name, given, None)
        if isinstance(allowed, PermissionResultDeny):
            self.used.append(("interrupt" if allowed.interrupt else "denied", allowed.message))
            return not allowed.interrupt
        args = {"name": name.removeprefix("mcp__bot__"), "arguments": allowed.updated_input}
        got = await self.rpc("tools/call", args)
        self.used.append(("error" if got.get("isError") else "result", got["content"][0]["text"]))
        return True

    async def receive_response(self) -> Any:
        steps = self.after if self.interrupted else self.script
        for step in steps:
            if step == HANG:
                await asyncio.Event().wait()
            elif isinstance(step, tuple):
                if not await self._use(step[1], step[2]):
                    yield result(None, "error_during_execution", terminal_reason="aborted_tools")
                    return
            elif callable(step):
                await step(self)  # a look at the session from inside the turn
            else:
                yield step


def cli(*script: Any, after: tuple[Any, ...] = (), starts: bool = True) -> type[Cli]:
    """A ClaudeSDKClient whose turns each play `script`."""
    return type("Played", (Cli,), {"script": list(script), "after": list(after), "starts": starts, "made": []})
