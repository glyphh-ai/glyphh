"""Tests for the MCP decision tools (decide / record_decision)."""

import asyncio

import pytest

import glyphh.decision.store as store
from domains.mcp.decision_tools import (
    DECISION_TOOL_NAMES,
    decision_tool_definitions,
    handle_decision_tool,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("GLYPHH_DECISIONS_DB", str(tmp_path / "decisions.db"))
    store.reset_default_space()
    yield
    store.reset_default_space()


def test_tool_definitions_match_names():
    assert {t.name for t in decision_tool_definitions()} == DECISION_TOOL_NAMES


def test_decide_with_no_precedent_declines():
    result = run(handle_decision_tool("decide", {"situation": {"k": "v"}}))
    assert result["sufficient"] is False


def test_record_then_decide_round_trip():
    for _ in range(3):
        run(handle_decision_tool("record_decision", {
            "situation": {"amount": "small"}, "outcome": "approved",
            "facts": {"case": "demo"},
        }))
    result = run(handle_decision_tool(
        "decide", {"situation": {"amount": "small"}}))
    assert result["sufficient"] is True
    assert result["top_outcome"] == "approved"
    assert "fact_tree" in result


def test_decide_requires_situation():
    with pytest.raises(ValueError):
        run(handle_decision_tool("decide", {}))


def test_record_requires_outcome():
    with pytest.raises(ValueError):
        run(handle_decision_tool("record_decision",
                                 {"situation": {"a": "b"}}))
