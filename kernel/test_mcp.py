"""MCP server tests for the Ada plugin. The server runs as a
subprocess speaking newline-delimited JSON-RPC over stdio, the way
Claude Code launches it from plugin/.mcp.json."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent
SERVER = REPO / "plugin" / "mcp" / "server.py"
SITUATION = {"task": "deploy_service", "constraint": "canary_required"}


def session(home: Path, *messages: dict) -> list:
    """Run one server session over `messages`; replies keyed by order."""
    env = {**os.environ, "GLYPHH_HOME": str(home)}
    wire = "".join(json.dumps(m) + "\n" for m in messages)
    proc = subprocess.run([sys.executable, str(SERVER)], input=wire,
                          capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines()]


def tool(rid: int, name: str, **arguments) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "method": "tools/call",
            "params": {"name": name, "arguments": arguments}}


def payload(reply: dict) -> dict:
    result = reply["result"]
    assert result["isError"] is False, result["content"][0]["text"]
    return json.loads(result["content"][0]["text"])


@pytest.fixture()
def home(tmp_path):
    sys.path.insert(0, str(REPO))
    from glyphh_kernel import Space
    mem = tmp_path / "ada"
    with Space(author="test-agent", path=str(mem / "wins.db")) as wins:
        wins.record(SITUATION, "canary_then_full_rollout")
    with Space(author="test-agent", path=str(mem / "vetoes.db")) as vetoes:
        vetoes.record(SITUATION, "big_bang_deploy")
    return tmp_path


def test_handshake_and_tool_list(home):
    init, listed = session(
        home,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert "tools" in init["result"]["capabilities"]
    names = {t["name"] for t in listed["result"]["tools"]}
    assert names == {"query", "facts", "calibrate", "record", "veto", "check",
                     "status"}


def test_query_returns_precedent_with_veto_check(home):
    (reply,) = session(home, tool(1, "query", situation=SITUATION))
    answer = payload(reply)
    assert answer["top"] == "canary_then_full_rollout"
    assert answer["sufficient"] and answer["act"]
    assert answer["veto_match"] == 0.0
    assert answer["calibrated"] is False  # precedent of one
    assert answer["receipts"][0]["author"] == "test-agent"


def test_record_and_veto_persist_with_author(home):
    new = {"task": "long_background_run", "constraint": "exceeds_tool_timeout"}
    rec, veto, status = session(
        home,
        tool(1, "record", situation=new, outcome="setsid_nohup",
             author="claude-test"),
        tool(2, "veto", situation=new, outcome="chained_sleep_polling",
             author="claude-test"),
        tool(3, "status"))
    assert payload(rec)["store"] == "wins"
    assert payload(veto)["store"] == "vetoes"
    assert payload(status)["wins"] == 2 and payload(status)["vetoes"] == 2
    # a fresh session sees the writes, authored
    (query,) = session(home, tool(1, "query", situation=new))
    answer = payload(query)
    assert answer["top"] == "setsid_nohup"
    assert answer["receipts"][0]["author"] == "claude-test"


def test_check_finds_the_veto(home):
    (reply,) = session(home, tool(1, "check", situation=SITUATION,
                                  outcome="big_bang_deploy"))
    result = payload(reply)
    assert result["veto_match"] > 0.9 and result["win_match"] == 0.0


def test_query_sees_rows_written_after_launch(home):
    """refresh() before each read: another session's write counts."""
    sys.path.insert(0, str(REPO))
    from glyphh_kernel import Space
    env = {**os.environ, "GLYPHH_HOME": str(home)}
    proc = subprocess.Popen([sys.executable, str(SERVER)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, env=env)
    try:
        def ask(msg):
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())
        assert payload(ask(tool(1, "status")))["wins"] == 1
        with Space(author="other", path=str(home / "ada" / "wins.db")) as wins:
            wins.record({"task": "x"}, "y")
        assert payload(ask(tool(2, "status")))["wins"] == 2
    finally:
        proc.stdin.close()
        proc.wait(timeout=30)


def test_bad_arguments_are_tool_errors(home):
    empty, bad_type, missing = session(
        home,
        tool(1, "query", situation={}),
        tool(2, "record", situation={"task": {}}, outcome="o", author="a"),
        tool(3, "veto", situation=SITUATION, outcome="o"))
    for reply in (empty, bad_type, missing):
        assert reply["result"]["isError"] is True


def test_unknown_tool_and_method(home):
    unknown_tool, unknown_method = session(
        home, tool(1, "nope"),
        {"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
    assert unknown_tool["error"]["code"] == -32602
    assert unknown_method["error"]["code"] == -32601


def test_mcp_json_points_at_the_server():
    config = json.loads((REPO / "plugin" / ".mcp.json").read_text())
    args = config["mcpServers"]["ada"]["args"]
    assert args == ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"]
    assert (REPO / "plugin" / "mcp" / "server.py").exists()


def test_query_reports_reason_and_a_newer_win_lifts_a_veto(home):
    """A veto of the recommended outcome blocks `act` until a newer win
    for it arrives — vetoes are outranked by later evidence, not
    permanent."""
    (first,) = session(home, tool(1, "query", situation=SITUATION))
    assert payload(first)["reason"] == "reflex"
    (_, blocked) = session(
        home,
        tool(1, "veto", situation=SITUATION,
             outcome="canary_then_full_rollout", author="grader"),
        tool(2, "query", situation=SITUATION))
    assert payload(blocked)["act"] is False
    assert payload(blocked)["reason"] == "vetoed"
    (_, lifted) = session(
        home,
        tool(1, "record", situation=SITUATION,
             outcome="canary_then_full_rollout", author="reproducer"),
        tool(2, "query", situation=SITUATION))
    answer = payload(lifted)
    assert answer["act"] is True and answer["lifted"] is True


def test_facts_and_weighted_query(home):
    decisive = {"goal": "move_data", "risk": "downtime",
                "team": "platform", "region": "us"}
    incidental = {"goal": "other", "risk": "lock_table",
                  "team": "infra", "region": "eu"}
    query = {"goal": "move_data", "risk": "downtime",
             "team": "infra", "region": "eu"}
    weights = {"goal": 1, "risk": 1, "team": 0.1, "region": 0}
    calls = [tool(i, "record", situation=s, outcome=o, author="t")
             for i, (s, o) in enumerate(
                 [(decisive, "dual_write"), (incidental, "batch_copy")] * 3)]
    replies = session(
        home, *calls,
        tool(10, "query", situation=query, weights=weights),
        tool(11, "facts", situation=query, weights=weights, top=2),
        tool(12, "facts", situation=query, weights={"risk": -1}),
        tool(13, "record", situation={"plan": {"step": "x"}, "n": 3},
             outcome="nested", author="t"))
    answer = json.loads(replies[6]["result"]["content"][0]["text"])
    assert answer["top"] == "dual_write"
    facts = json.loads(replies[7]["result"]["content"][0]["text"])
    assert [f["outcome"] for f in facts["wins"]] == ["dual_write"] * 2
    assert facts["wins"][0]["score"] > 0.9 and facts["vetoes"] == []
    keys = [c["key"] for c in facts["wins"][0]["tree"]["children"]]
    assert keys == ["goal", "region", "risk", "team"]
    assert replies[8]["result"]["isError"] is True
    assert replies[9]["result"]["isError"] is False
