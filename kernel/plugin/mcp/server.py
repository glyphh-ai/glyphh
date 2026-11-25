"""The Ada memory as an MCP server (stdio, JSON-RPC 2.0, stdlib only).

Claude Code launches this from the plugin's .mcp.json, outside the
agent's shell sandbox — so the agent can read AND write the one memory
($GLYPHH_HOME/ada, else ~/.glyphh/ada) without a sandbox exception,
a port, or a token. The composing primitives (bind, bundle, sim) stay
in the kernel for the agent's own shell; only the stores live here.
Situations may nest, and every read takes a weights tree; `facts`
returns the weighted read as fact trees.

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

    def query(self, situation: Dict[str, Any],
              weights: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from glyphh_kernel import decide
        s = self.spaces()
        # the kernel's contract, with count reported (not gated) so a
        # precedent of one still surfaces as a cited reminder
        d = decide(s["wins"], s["vetoes"], situation,
                   min_confidence=ACT_CONFIDENCE, min_count=1,
                   weights=weights)
        out = d.answer.to_json()
        veto = (s["vetoes"].matches(situation, d.answer.top,
                                    weights=weights)
                if d.answer.top else 0.0)
        out["veto_match"] = round(veto, 4)
        out["act"] = d.act
        out["reason"] = d.reason
        out["lifted"] = d.lifted  # a newer win outranks a close veto
        out["calibrated"] = d.answer.count >= CALIBRATED_COUNT
        return out

    def facts(self, situation: Dict[str, Any],
              weights: Optional[Dict[str, Any]], top: int) -> Dict[str, Any]:
        s = self.spaces()
        return {store: [f.to_json() for f in
                        s[store].facts(situation, weights=weights, top=top,
                                       min_score=MIN_SIM)]
                for store in ("wins", "vetoes")}

    def calibrate(self, weights: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        wins = self.spaces()["wins"]
        return {"store": "wins", "tau": wins.calibrate(weights=weights),
                "size": len(wins)}

    def record(self, store: str, situation: Dict[str, Any], outcome: str,
               author: str) -> Dict[str, Any]:
        space = self.spaces()[store]
        space.author = author
        return {"store": store, "id": space.record(situation, outcome),
                "size": len(space)}

    def check(self, situation: Dict[str, Any], outcome: str) -> Dict[str, Any]:
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
                   '"constraint": "exceeds_tool_timeout"}. Values may '
                   "nest (objects, arrays as sets, numbers, booleans). "
                   "Incidental attributes (ids, paths, timestamps) poison "
                   "neighborhoods.",
    "minProperties": 1,
}
WEIGHTS = {
    "type": "object",
    "description": "How much each key decides, mirroring the situation: "
                   '{"risk": 1, "team": 0.1, "plan": {"*": 0.5, "step": 2}}. '
                   "A number weighs a key; an object weighs inside it, its "
                   'own weight under "*". Unlisted keys weigh 1; 0 ignores '
                   "a key.",
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
     "inputSchema": {"type": "object",
                     "properties": {"situation": SITUATION,
                                    "weights": WEIGHTS},
                     "required": ["situation"]}},
    {"name": "facts",
     "description": "Why, not just what: the nearest wins and vetoes, each "
                    "explained against this situation as a fact tree — per "
                    "key its score, weight and share of the whole — and "
                    "ranked by exact weighted score, each with its id, "
                    "author, and `probability` of its outcome. Only "
                    "precedents scoring 0.4 or more.",
     "inputSchema": {"type": "object",
                     "properties": {"situation": SITUATION,
                                    "weights": WEIGHTS,
                                    "top": {"type": "integer", "minimum": 1,
                                            "maximum": 50,
                                            "description": "Precedents per "
                                            "store (default 3)."}},
                     "required": ["situation"]}},
    {"name": "calibrate",
     "description": "Fit the wins store's probability temperature to its "
                    "own graded record (needs 10+ wins), so `probability` "
                    "in `facts` means what it says. Saved in the store; "
                    "rerun after the store grows a lot. Pass the weights "
                    "you query with.",
     "inputSchema": {"type": "object", "properties": {"weights": WEIGHTS}}},
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


def _situation(args: Dict[str, Any]) -> Dict[str, Any]:
    s = args.get("situation")
    if not isinstance(s, dict) or not s:
        raise ValueError("situation must be a non-empty object")
    from glyphh_kernel import encode
    encode(s)  # nested, non-empty, encodable — or the error says why
    return s


def _weights(args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    w = args.get("weights")
    if w is None:
        return None
    if not isinstance(w, dict):
        raise ValueError("weights must be an object")
    return w


def _top(args: Dict[str, Any]) -> int:
    top = args.get("top", 3)
    if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= 50:
        raise ValueError("top must be an integer from 1 to 50")
    return top


def _string(args: Dict[str, Any], key: str) -> str:
    v = args.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return v.strip()


def call(memory: Memory, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "query":
        return memory.query(_situation(args), _weights(args))
    if name == "calibrate":
        return memory.calibrate(_weights(args))
    if name == "facts":
        return memory.facts(_situation(args), _weights(args), _top(args))
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
