"""The Ada memory as an MCP server (stdio, JSON-RPC 2.0, stdlib only).

Claude Code launches this from the plugin's .mcp.json, outside the
agent's shell sandbox — so the agent can read AND write the one memory
($GLYPHH_HOME/ada, else ~/.glyphh/ada) without a sandbox exception,
a port, or a token. The composing primitives (bind, bundle, sim) stay
in the kernel for the agent's own shell; only the stores live here.

The spaces load once and refresh() before every read, so rows other
sessions wrote since launch always count.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROTOCOL = "2025-06-18"
MIN_SIM, K = 0.40, 7
ACT_CONFIDENCE = 0.5   # the skill's bar for acting on a top answer
CALIBRATED_COUNT = 3   # below this, precedent is a cited reminder


def memory_dir() -> Path:
    home = os.environ.get("GLYPHH_HOME") or str(Path.home() / ".glyphh")
    return Path(home) / "ada"


class Memory:
    """wins + vetoes, opened lazily so the server starts even when numpy
    is missing — the error then surfaces on the first tool call."""

    def __init__(self, path: Path):
        self.path = path
        self._spaces: Optional[Dict[str, Any]] = None

    def spaces(self) -> Dict[str, Any]:
        if self._spaces is None:
            from glyphh_kernel import Space
            self._spaces = {
                name: Space(min_sim=MIN_SIM, k=K,
                            path=str(self.path / f"{name}.db"))
                for name in ("wins", "vetoes")}
        for space in self._spaces.values():
            space.refresh()
        return self._spaces

    def query(self, situation: Dict[str, str]) -> Dict[str, Any]:
        from glyphh_kernel import decide
        s = self.spaces()
        # the kernel's contract, with count reported (not gated) so a
        # precedent of one still surfaces as a cited reminder
        d = decide(s["wins"], s["vetoes"], situation,
                   min_confidence=ACT_CONFIDENCE, min_count=1)
        out = d.answer.to_json()
        veto = (s["vetoes"].matches(situation, d.answer.top)
                if d.answer.top else 0.0)
        out["veto_match"] = round(veto, 4)
        out["act"] = d.act
        out["reason"] = d.reason
        out["lifted"] = d.lifted  # a newer win outranks a close veto
        out["calibrated"] = d.answer.count >= CALIBRATED_COUNT
        return out

    def record(self, store: str, situation: Dict[str, str], outcome: str,
               author: str) -> Dict[str, Any]:
        space = self.spaces()[store]
        space.author = author
        return {"store": store, "id": space.record(situation, outcome),
                "size": len(space)}

    def check(self, situation: Dict[str, str], outcome: str) -> Dict[str, Any]:
        s = self.spaces()
        return {"win_match": round(s["wins"].matches(situation, outcome), 4),
                "veto_match": round(s["vetoes"].matches(situation, outcome), 4)}

    def status(self) -> Dict[str, Any]:
        s = self.spaces()
        return {"memory_dir": str(self.path), "wins": len(s["wins"]),
                "vetoes": len(s["vetoes"])}


SITUATION = {
    "type": "object",
    "description": "Decision-relevant attributes only, e.g. "
                   '{"task": "long_background_run", '
                   '"constraint": "exceeds_tool_timeout"}. Incidental '
                   "attributes (ids, paths, timestamps) poison neighborhoods.",
    "additionalProperties": {"type": "string"},
    "minProperties": 1,
}
OUTCOME = {"type": "string",
           "description": "The approach, as a short snake_case label."}
AUTHOR = {"type": "string",
          "description": "Your agent name; receipts carry it."}

TOOLS = [
    {"name": "query",
     "description": "Ask the wins store what worked in similar situations. "
                    "Returns the top outcome with confidence, support, "
                    "count, receipts, the nearest veto of that outcome, "
                    "and `act` (sufficient, confidence >= 0.5, and no veto "
                    "as close as the wins unless a newer win outranks it; "
                    "`reason` says which gate decided, `lifted` whether a "
                    "newer win lifted a veto). With `calibrated` false "
                    "treat it as a cited reminder, not a settled rule.",
     "inputSchema": {"type": "object", "properties": {"situation": SITUATION},
                     "required": ["situation"]}},
    {"name": "record",
     "description": "Record a graded WIN: this outcome worked in this "
                    "situation. Only after the outcome is actually known.",
     "inputSchema": {"type": "object",
                     "properties": {"situation": SITUATION,
                                    "outcome": OUTCOME, "author": AUTHOR},
                     "required": ["situation", "outcome", "author"]}},
    {"name": "veto",
     "description": "Record a graded FAILURE: this outcome failed (or the "
                    "user rejected it) in this situation.",
     "inputSchema": {"type": "object",
                     "properties": {"situation": SITUATION,
                                    "outcome": OUTCOME, "author": AUTHOR},
                     "required": ["situation", "outcome", "author"]}},
    {"name": "check",
     "description": "How close is the nearest recorded win and the nearest "
                    "recorded veto of THIS outcome to this situation? Use "
                    "before an approach you are considering.",
     "inputSchema": {"type": "object",
                     "properties": {"situation": SITUATION,
                                    "outcome": OUTCOME},
                     "required": ["situation", "outcome"]}},
    {"name": "status",
     "description": "Where the memory lives and how many wins and vetoes "
                    "it holds.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _situation(args: Dict[str, Any]) -> Dict[str, str]:
    s = args.get("situation")
    if not isinstance(s, dict) or not s:
        raise ValueError("situation must be a non-empty object")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in s.items()):
        raise ValueError("situation keys and values must be strings")
    return s


def _string(args: Dict[str, Any], key: str) -> str:
    v = args.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return v.strip()


def call(memory: Memory, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "query":
        return memory.query(_situation(args))
    if name in ("record", "veto"):
        store = "wins" if name == "record" else "vetoes"
        return memory.record(store, _situation(args),
                             _string(args, "outcome"), _string(args, "author"))
    if name == "check":
        return memory.check(_situation(args), _string(args, "outcome"))
    if name == "status":
        return memory.status()
    raise KeyError(name)


def handle(memory: Memory, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One JSON-RPC message in, one response out (None for notifications)."""
    method, rid = msg.get("method"), msg.get("id")
    if rid is None:
        return None  # notifications/initialized and friends

    def ok(result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        return ok({"protocolVersion": version,
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": "ada", "version": "3.0.1"}})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in {t["name"] for t in TOOLS}:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": f"unknown tool: {name}"}}
        try:
            text, is_error = json.dumps(call(memory, name, args)), False
        except ImportError as e:
            text, is_error = (f"Ada kernel unavailable ({e}); "
                              "install numpy for python3"), True
        except Exception as e:  # tool errors go back to the model, not the wire
            text, is_error = f"{type(e).__name__}: {e}", True
        return ok({"content": [{"type": "text", "text": text}],
                   "isError": is_error})
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> None:
    memory = Memory(memory_dir())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = handle(memory, msg) if isinstance(msg, dict) else None
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
