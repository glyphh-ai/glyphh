"""Ada as Claude's tools: an MCP server (stdio, no dependencies) over the ada-private kernel, keeping its models in
one folder (ADA_HOME) that outlives every session. Claude decides what a model is, what to record in it and when to
ask it; nothing here decides for it.

Tools: ada_models, ada_make, ada_record, ada_ask, ada_beam, ada_forget, ada_note.

    python ada_mcp.py            # serves stdio for `claude --mcp-config`
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ada_kernel  # noqa: E402

HOME = Path(os.environ.get("ADA_HOME", "ada_home")).resolve()
NOTE_LIMIT = 500  # characters: a hint, not a notebook

ROLE = {"type": "object", "description": "A case in the model's shape: {layer: {segment: {role: value}}}, one value per role"}
TOOLS = [
    {
        "name": "ada_models",
        "description": "Your Ada models: each one's name, spec and how many cases it holds, plus your note to yourself.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ada_make",
        "description": (
            "Make an Ada model from a spec: {name, layers: [{name, segments: [{name, roles: [{name}]}]}]}. A model learns "
            "cases (ada_record) and answers new ones from the nearest it holds (ada_ask). Keep each model to one kind of "
            "question. A model that exists is kept as it is."
        ),
        "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
    },
    {
        "name": "ada_record",
        "description": "Record a case and its outcome in a model, so it answers cases like it next time. Returns the case's id.",
        "inputSchema": {
            "type": "object",
            "properties": {"model": {"type": "string"}, "data": ROLE, "outcome": {"type": "string"}},
            "required": ["model", "data", "outcome"],
        },
    },
    {
        "name": "ada_ask",
        "description": "Ask a model about a case: the outcome it decides, how probable each outcome is, and whether it is unsure (ask).",
        "inputSchema": {"type": "object", "properties": {"model": {"type": "string"}, "data": ROLE}, "required": ["model", "data"]},
    },
    {
        "name": "ada_beam",
        "description": (
            "Chain models: ask the first about a value, feed each outcome into the next, keeping the likeliest paths (width). "
            "hops: [{model, role: 'layer.segment.role' the value goes into, fixed: {role: value} for the segment's other roles}]. values: every value "
            "a hop may land on; miss: how far to doubt each hop (0 to 1). Answers the end, its probability and the best paths."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "hops": {"type": "array", "items": {"type": "object"}},
                "width": {"type": "integer", "default": 10},
                "values": {"type": "array", "items": {"type": "string"}},
                "miss": {"type": "number", "default": 0.05},
            },
            "required": ["start", "hops"],
        },
    },
    {
        "name": "ada_forget",
        "description": "Take one case out of a model by its id, or drop a whole model (no id).",
        "inputSchema": {"type": "object", "properties": {"model": {"type": "string"}, "id": {"type": "string"}}, "required": ["model"]},
    },
    {
        "name": "ada_note",
        "description": f"Replace your note to yourself (at most {NOTE_LIMIT} characters): what your models are for and how you use them.",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
]


class Ada:
    def __init__(self) -> None:
        self.spec = ada_kernel.load()
        self.models: dict = {}
        HOME.mkdir(parents=True, exist_ok=True)

    def specs(self) -> dict[str, dict]:
        file = HOME / "specs.json"
        return json.loads(file.read_text()) if file.exists() else {}

    def model(self, name: str):
        if name not in self.models:
            specs = self.specs()
            if name not in specs:
                raise ValueError(f"no model {name!r}: ada_models lists them")
            self.models[name] = self.spec.Model(self.spec.Spec.from_json(specs[name]), path=str(HOME / f"{name}.sqlite"))
        return self.models[name]

    def ada_models(self) -> dict:
        note = HOME / "note.txt"
        return {
            "models": [{"name": n, "spec": s, "cases": len(self.model(n))} for n, s in self.specs().items()],
            "note": note.read_text() if note.exists() else "",
        }

    def ada_make(self, spec: dict) -> dict:
        specs = self.specs()
        name = spec.get("name")
        if name in specs:
            return {"made": False, "name": name, "cases": len(self.model(name))}
        parsed = self.spec.Spec.from_json({"seed": 5, "dimension": 1024} | spec)
        specs[name] = parsed.to_json()
        (HOME / "specs.json").write_text(json.dumps(specs, indent=1))
        return {"made": True, "name": name}

    def ada_record(self, model: str, data: dict, outcome: str) -> dict:
        return {"id": self.model(model).record(data, outcome)}

    def ada_ask(self, model: str, data: dict) -> dict:
        return self.model(model).decide(data)

    def ada_beam(self, start: str, hops: list[dict], width: int = 10, values: list[str] | None = None, miss: float = 0.05) -> dict:
        def asker(role: str, fixed: dict):
            layer, segment, name = role.split(".")

            def ask(value: str) -> dict:
                return {layer: {segment: dict(fixed) | {name: value}}}

            return ask

        chain = [self.spec.Hop(self.model(h["model"]), asker(h["role"], h.get("fixed", {}))) for h in hops]
        answer = self.spec.beam(start, chain, width, values or (), miss)
        answer["paths"] = answer["paths"][:5]
        return answer

    def ada_forget(self, model: str, id: str | None = None) -> dict:
        if id is not None:
            self.model(model).forget(id)
            return {"forgot": id}
        specs = self.specs()
        specs.pop(model, None)
        (HOME / "specs.json").write_text(json.dumps(specs, indent=1))
        self.models.pop(model, None)
        (HOME / f"{model}.sqlite").unlink(missing_ok=True)
        return {"dropped": model}

    def ada_note(self, text: str) -> dict:
        (HOME / "note.txt").write_text(text[:NOTE_LIMIT])
        return {"kept": len(text[:NOTE_LIMIT])}


def serve() -> None:
    ada = Ada()
    log = open(HOME / "calls.jsonl", "a")
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        rid, method, params = request.get("id"), request.get("method"), request.get("params") or {}
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "ada", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            name, args = params["name"], params.get("arguments") or {}
            try:
                out = getattr(ada, name)(**args)
                result = {"content": [{"type": "text", "text": json.dumps(out)}]}
            except Exception as e:  # noqa: BLE001  (the tool's error is the answer)
                result = {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}
            log.write(json.dumps({"session": os.environ.get("ADA_SESSION"), "tool": name, "args": args, "error": result.get("isError", False)}) + "\n")
            log.flush()
        elif rid is None:
            continue  # a notification
        else:
            result = {}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    serve()
