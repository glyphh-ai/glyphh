"""Fakes for the bots' tests: Ada in memory (models, precedents, decisions) and `claude -p` (no network, no Claude)."""

from __future__ import annotations

import json
import subprocess
import textwrap
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

from glyphh.client import Decision, ModelInfo
from glyphh.errors import ConflictError, ModelMissingError, SpecError


class FakeModel:
    def __init__(self, ada: "FakeAda", name: str) -> None:
        self.ada, self.name = ada, name

    def _there(self) -> None:
        if self.name not in self.ada.specs:
            raise ModelMissingError("E_MODEL_MISSING", f"no model {self.name}", 404)

    def info(self) -> ModelInfo:
        self._there()
        return ModelInfo({"name": self.name, "precedents": len(self.ada.cases[self.name])})

    def record(self, data: Dict[str, Any], outcome: Optional[str] = None) -> SimpleNamespace:
        self._there()
        self.ada.cases[self.name].append((data, outcome))
        return SimpleNamespace(data={"id": f"p{len(self.ada.cases[self.name])}"})

    def decide(self, data: Dict[str, Any]) -> Decision:
        self._there()
        self.ada.decided.append((self.name, data))
        if self.name in self.ada.rule:
            outcome, p = self.ada.rule[self.name](data)
            ask_below = float((self.ada.specs[self.name].get("output") or {}).get("ask_below", 0.6))
            return Decision.of({"outcome": outcome, "probabilities": {outcome: p}, "ask": p < ask_below}, self.name)
        if self.name in self.ada.sure:
            outcome = self.ada.sure[self.name]
            return Decision.of({"outcome": outcome, "probabilities": {outcome: 0.95}, "ask": False}, self.name)
        votes: Dict[str, int] = defaultdict(int)
        for _, o in self.ada.cases[self.name]:
            votes[str(o)] += 1
        best = max(votes, key=lambda k: votes[k]) if votes else None
        return Decision.of({"outcome": best, "probabilities": {best: 0.5} if best else {}, "ask": True}, self.name)

    def facts(self, data: Dict[str, Any], top: Optional[int] = None) -> SimpleNamespace:
        self._there()
        trees = [{"outcome": o, "score": 1.0} for _, o in reversed(self.ada.cases[self.name])]
        return SimpleNamespace(data=trees[: top or len(trees)])


class FakeAda:
    """Ada Cloud in memory. `sure[model] = outcome` makes a model decide that, sure; `rule[model] = f(case) ->
    (outcome, p)` decides each case, asking under the spec's ask_below; else it asks."""

    def __init__(self) -> None:
        self.specs: Dict[str, Dict[str, Any]] = {}
        self.cases: Dict[str, List[Tuple[Dict[str, Any], Any]]] = defaultdict(list)
        self.sure: Dict[str, str] = {}
        self.rule: Dict[str, Callable[[Dict[str, Any]], Tuple[str, float]]] = {}
        self.decided: List[Tuple[str, Dict[str, Any]]] = []

    def models(self) -> List[ModelInfo]:
        return [ModelInfo({"name": n, "precedents": len(self.cases[n])}) for n in self.specs]

    def model(self, name: str) -> FakeModel:
        return FakeModel(self, name)

    def create_model(self, name: str, spec: Dict[str, Any]) -> FakeModel:
        if len(name) > 63:
            raise SpecError("E_SPEC", f"{name} is too long", 400)
        if name in self.specs:
            raise ConflictError("E_CONFLICT", f"{name} is there", 409)
        assert spec["name"] == name
        self.specs[name] = spec
        return FakeModel(self, name)

    def outcomes(self, name: str) -> List[Any]:
        return [o for _, o in self.cases[name]]


class FakeClaude:
    """`claude -p`, faked: each call is kept (argv, cwd); `answers` are its results in turn; `build` writes files into
    the builder's folder."""

    def __init__(self) -> None:
        self.calls: List[Tuple[List[str], str]] = []
        self.answers: List[str] = []
        self.build: Optional[Callable[[Path], None]] = None
        self.fail: Optional[str] = None
        self.cost: float = 0.0

    def __call__(self, argv: List[str], **kw: Any) -> "subprocess.CompletedProcess[str]":
        self.calls.append((argv, kw["cwd"]))
        if self.fail:
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr=self.fail)
        if "Read,Write" in argv and self.build:
            self.build(Path(kw["cwd"]))
        result = self.answers.pop(0) if self.answers else "an answer"
        said = {"result": result, "total_cost_usd": self.cost} if self.cost else {"result": result}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(said), stderr="")


@pytest.fixture
def fake_ada() -> FakeAda:
    return FakeAda()


@pytest.fixture
def fake_claude() -> FakeClaude:
    return FakeClaude()


DIGEST_SPEC = {
    "name": "worth",
    "layers": [{"name": "d", "segments": [{"name": "s", "roles": [
        {"name": "new", "numeric_config": {"min_value": 0, "max_value": 50, "bin_width": 1}},
        {"name": "run", "key_part": True, "similarity_weight": 0},
    ]}]}],
    "output": {"costs": {"skip": {"send": 2}, "send": {"skip": 1}}, "ask_below": 0.7},
}

DIGEST_PROGRAM = '''
def fetch(ctx, inputs):
    got = ctx.http_json("https://api.example.com/items")
    ctx.log(f"fetched {len(got['items'])}")
    if not got["items"]:
        return {"_end": "nothing new"}
    return got


def worth_case(ctx, data):
    return {"d": {"s": {"new": len(data["fetch"]["items"]), "run": ctx.run_id}}}


def deliver(ctx, inputs):
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    (out / "digest.md").write_text(inputs)
    db = ctx.db()
    db.execute("CREATE TABLE IF NOT EXISTS sent (run TEXT)")
    db.execute("INSERT INTO sent VALUES (?)", (ctx.run_id,))
    db.commit()
    ctx.set_state("last", ctx.run_id)
    return {"path": str(out / "digest.md"), "today": ctx.today.isoformat()}


def boom(ctx, inputs):
    raise RuntimeError("it broke")
'''


def digest_spec(**over: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "slug": "digest",
        "name": "Digest",
        "summary": "Each morning, the new items, summed up",
        "agent": "agent.md",
        "touches": "sends",
        "hosts": ["api.example.com"],
        "seed": {"personality": ["Short."], "instructions": ["Lead with the count."]},
        "gates": {"worth": {"case": "worth_case", "outcomes": ["send", "skip"], "question": "Worth it?",
                            "spec": DIGEST_SPEC}},
        "loop": [
            {"id": "fetch", "run": "fetch"},
            {"id": "worth", "gate": "worth", "on": {"send": "write", "skip": "end"}},
            {"id": "write", "agent": "Sum up: $fetch", "skill": "digest", "remember": True},
            {"id": "deliver", "run": "deliver", "input": "$write", "approval": "send the digest"},
        ],
        "routine": {"cron": "30 7 * * 1-5"},
        "limits": {"seconds": 60, "agent_turns": 2},
    }
    spec.update(over)
    return spec


def write_bot(folder: Path, spec: Optional[Dict[str, Any]] = None, program: str = DIGEST_PROGRAM) -> Path:
    spec = spec or digest_spec()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "bot.json").write_text(json.dumps(spec))
    (folder / "agent.md").write_text(textwrap.dedent("""\
        ---
        name: digest
        description: Sums up the new items
        tools: []
        model: sonnet
        ---

        You are Digest. Answer only what the step asks.
        """))
    (folder / "program.py").write_text(program)
    skill = folder / "skills" / "digest"
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("---\nname: digest\ndescription: How\n---\n\nOne line per item.\n")
    return folder


@pytest.fixture
def bot_folder(tmp_path: Path) -> Path:
    return write_bot(tmp_path / "src" / "digest")


@pytest.fixture
def bots_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "bots"
    monkeypatch.setenv("GLYPHH_BOTS", str(root))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GLYPHH_API_KEY", raising=False)
    return root
