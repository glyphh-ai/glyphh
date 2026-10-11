import logging

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from glyphh_server.errors import Forbidden
from glyphh_server.mcp.guard import guarded
from glyphh_server.obs.context import bound


@guarded("echo")
async def echo(text: str) -> str:
    return text


@guarded("refuse")
async def refuse() -> None:
    raise Forbidden("Only an org admin can do that.")


@guarded("crash")
async def crash() -> None:
    raise RuntimeError("database password is hunter2")


async def test_a_tool_keeps_its_signature_and_answers(caplog: pytest.LogCaptureFixture) -> None:
    import inspect

    assert list(inspect.signature(echo).parameters) == ["text"]
    with caplog.at_level(logging.INFO, logger="glyphh.mcp"):
        assert await echo("hi") == "hi"
    assert caplog.records[-1].fields["tool"] == "echo"  # type: ignore[attr-defined]


async def test_a_refusal_reaches_the_agent_with_its_code_and_trace() -> None:
    with bound(trace="mcp-trace-0001"), pytest.raises(ToolError) as caught:
        await refuse()
    assert str(caught.value) == "E_FORBIDDEN: Only an org admin can do that. (trace mcp-trace-0001)"


async def test_a_crash_fails_closed_and_is_logged_with_its_traceback(caplog: pytest.LogCaptureFixture) -> None:
    with bound(trace="mcp-trace-0002"), caplog.at_level(logging.INFO), pytest.raises(ToolError) as caught:
        await crash()
    assert str(caught.value).startswith("E_INTERNAL:") and "hunter2" not in str(caught.value)
    assert "mcp-trace-0002" in str(caught.value)
    logged = [r for r in caplog.records if r.getMessage() == "tool crashed"]
    assert logged and logged[0].exc_info is not None
