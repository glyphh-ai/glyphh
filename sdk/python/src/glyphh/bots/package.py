"""A bot's package: a folder holding `bot.json` (its loop of steps, its gates, what it touches), `agent.md` (its Claude
agent), `program.py` (its code steps) and `skills/<name>/SKILL.md` (how the agent does one kind of step). Loading one
checks all of it, and every problem found is said at once (`BotError`'s `problems`)."""

from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..errors import AdaError

#: What a bot may touch, from the least outward to the most.
TOUCHES = ("read_only", "drafts", "sends", "pays", "deletes")
#: What touches that far needs an approval step: the person says yes before it acts outward.
OUTWARD = ("sends", "pays", "deletes")
#: The kinds of memory every bot (and the orchestrator) keeps, each its own Ada model.
KINDS = ("memory", "instructions", "personality")
#: Ada model names: lower case letters, digits and `_ . -`, at most 63.
MODEL_NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,62}")
SLUG = re.compile(r"[a-z][a-z0-9_]*")
NAME = re.compile(r"[a-z][a-z0-9_]*")
STEP_KINDS = ("run", "gate", "agent")


class BotError(AdaError):
    """E_BOT: a bot's package is not right (`problems`, each one line), or a bot command cannot be done as asked."""

    def __init__(self, message: str, problems: Optional[List[str]] = None) -> None:
        super().__init__("E_BOT", message, 0, {"problems": problems} if problems else None)

    @property
    def problems(self) -> List[str]:
        return list(self.detail.get("problems") or [])


def bots_root() -> Path:
    """Where bots live: GLYPHH_BOTS, else ~/.glyphh/bots."""
    found = os.environ.get("GLYPHH_BOTS")
    return Path(found).expanduser() if found else Path.home() / ".glyphh" / "bots"


def model_name(*parts: str) -> str:
    """An Ada model's name from its parts, `_` read as `-`: model_name("bot", "launch_watch", "gate", "worth")."""
    return "-".join(p.replace("_", "-") for p in parts)


def check_model_name(name: str) -> Optional[str]:
    """Why an Ada model name would be refused, or None when it is good."""
    if len(name) > 63:
        return f"the Ada model name {name} is {len(name)} characters: at most 63"
    if not MODEL_NAME.fullmatch(name):
        return f"the Ada model name {name} is not lower case letters, digits and _ . -"
    return None


def frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """A Markdown file's `---` frontmatter, as plain `key: value` lines, and the body after it."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n?(.*)", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()


class Bot:
    """A bot's package, loaded and checked. `spec` is its bot.json; `program` its program.py, imported."""

    def __init__(self, folder: Path, spec: Dict[str, Any], program: ModuleType) -> None:
        self.dir, self.spec, self.program = folder, spec, program
        self.slug: str = spec["slug"]

    @classmethod
    def load(cls, folder: Path) -> "Bot":
        """The bot in this folder, every part checked; `BotError` names each problem."""
        folder = Path(folder)
        problems: List[str] = []
        try:
            spec = json.loads((folder / "bot.json").read_text("utf-8"))
        except FileNotFoundError:
            raise BotError(f"{folder} has no bot.json: it is not a bot") from None
        except ValueError as e:
            raise BotError(f"{folder}/bot.json is not JSON: {e}") from None
        if not isinstance(spec, dict):
            raise BotError(f"{folder}/bot.json is not a JSON object")
        problems += check_spec(spec, folder)
        program: Optional[ModuleType] = None
        if (folder / "program.py").exists():
            try:
                program = _import(folder, str(spec.get("slug") or folder.name))
            except Exception as e:  # noqa: BLE001  the bot's own code: whatever it raises is the problem
                problems.append(f"program.py does not import: {type(e).__name__}: {e}")
        else:
            problems.append("there is no program.py")
        if program is not None:
            problems += check_program(spec, program)
        if problems:
            raise BotError(f"the bot in {folder} is not right: {problems[0]}", problems)
        assert program is not None
        return cls(folder, spec, program)

    # its Ada models

    def gate_model(self, gate: str) -> str:
        return model_name("bot", self.slug, "gate", gate)

    def memory_model(self, kind: str) -> str:
        return model_name("bot", self.slug, kind)

    def models(self) -> List[str]:
        return [self.gate_model(g) for g in self.gates] + [self.memory_model(k) for k in KINDS]

    # its parts

    @property
    def name(self) -> str:
        return str(self.spec.get("name") or self.slug)

    @property
    def gates(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.spec.get("gates") or {})

    @property
    def loop(self) -> List[Dict[str, Any]]:
        return list(self.spec["loop"])

    @property
    def touches(self) -> str:
        return str(self.spec.get("touches") or "read_only")

    @property
    def hosts(self) -> List[str]:
        return list(self.spec.get("hosts") or [])

    @property
    def limits(self) -> Dict[str, Any]:
        return dict(self.spec.get("limits") or {})

    @property
    def reads_glyphh(self) -> bool:
        return bool(self.spec.get("reads_glyphh", True))

    def agent(self) -> Tuple[str, Dict[str, Any]]:
        """The bot's Claude agent: its name, and its definition for `claude --agents`."""
        meta, body = frontmatter((self.dir / str(self.spec.get("agent") or "agent.md")).read_text("utf-8"))
        definition: Dict[str, Any] = {"description": meta.get("description", ""), "prompt": body}
        if meta.get("model"):
            definition["model"] = meta["model"]
        return meta["name"], definition

    def skill(self, name: str) -> str:
        return (self.dir / "skills" / name / "SKILL.md").read_text("utf-8")


def _import(folder: Path, slug: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"glyphh_bot_{slug}", folder / "program.py")
    if spec is None or spec.loader is None:  # pragma: no cover  (a .py file always has a loader)
        raise ImportError("no loader for program.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_spec(spec: Mapping[str, Any], folder: Path) -> List[str]:
    """Every problem with a bot.json (and the files it names), one line each; [] when it is right."""
    problems: List[str] = []
    slug = spec.get("slug")
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        problems.append("slug must be snake_case: lower case letters, digits and _, starting with a letter")
        slug = "x"
    for kind in KINDS:
        why = check_model_name(model_name("bot", slug, kind))
        if why:
            problems.append(f"slug {slug} is too long: {why}")
            break
    if not isinstance(spec.get("name"), str) or not spec.get("name"):
        problems.append("name is missing")
    touches = spec.get("touches", "read_only")
    if touches not in TOUCHES:
        problems.append(f"touches must be one of {', '.join(TOUCHES)}")
    hosts = spec.get("hosts", [])
    if not isinstance(hosts, list) or not all(isinstance(h, str) and h for h in hosts):
        problems.append("hosts must be a list of host names")
    seed = spec.get("seed", {})
    if not isinstance(seed, dict) or any(k not in KINDS or not isinstance(v, list) for k, v in seed.items()):
        problems.append(f"seed must map {', '.join(KINDS)} to lists of lines")
    limits = spec.get("limits", {})
    if not isinstance(limits, dict) or any(not isinstance(v, int) or v <= 0 for v in limits.values()):
        problems.append("limits must be positive whole numbers (seconds, agent_turns)")
    routine = spec.get("routine")
    if routine is not None and (not isinstance(routine, dict) or len(str(routine.get("cron", "")).split()) != 5):
        problems.append('routine must be {"cron": "M H dom mon dow"}, five fields')

    agent = folder / str(spec.get("agent") or "agent.md")
    if not agent.exists():
        problems.append(f"there is no {agent.name}")
    elif not frontmatter(agent.read_text("utf-8"))[0].get("name"):
        problems.append(f"{agent.name} has no frontmatter name")

    gates = spec.get("gates", {})
    if not isinstance(gates, dict):
        problems.append("gates must be an object of gate name to gate")
        gates = {}
    for name, gate in gates.items():
        problems += _check_gate(slug, name, gate)

    loop = spec.get("loop")
    if not isinstance(loop, list) or not loop:
        problems.append("loop must be a list of steps, at least one")
        return problems
    ids = [s.get("id") for s in loop if isinstance(s, dict)]
    if len(ids) != len(loop) or not all(isinstance(i, str) and i for i in ids):
        problems.append("every step is an object with an id")
        return problems
    if len(set(ids)) != len(ids):
        problems.append("step ids must differ")
    approvals = 0
    for step in loop:
        problems += _check_step(step, ids, gates, folder)
        approvals += bool(step.get("approval"))
    if touches in OUTWARD and not approvals:
        problems.append(f"the bot touches {touches} but no step has an approval: it would act outward unasked")
    return problems


def _check_gate(slug: str, name: str, gate: Any) -> List[str]:
    if not NAME.fullmatch(name):
        return [f"gate {name}: its name must be snake_case"]
    if not isinstance(gate, dict):
        return [f"gate {name}: not an object"]
    problems = []
    why = check_model_name(model_name("bot", slug, "gate", name))
    if why:
        problems.append(f"gate {name}: {why}")
    if not isinstance(gate.get("case"), str):
        problems.append(f"gate {name}: case must name the program.py function that builds its case")
    outcomes = gate.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) < 2 or not all(isinstance(o, str) and o for o in outcomes):
        problems.append(f"gate {name}: outcomes must be two or more names")
    elif len(set(outcomes)) != len(outcomes):
        problems.append(f"gate {name}: outcomes must differ")
    s = gate.get("spec")
    if not isinstance(s, dict) or not isinstance(s.get("layers"), list) or not s["layers"]:
        problems.append(f"gate {name}: spec must be an Ada spec with layers")
    return problems


def _check_step(step: Dict[str, Any], ids: List[str], gates: Mapping[str, Any], folder: Path) -> List[str]:
    sid = step["id"]
    kinds = [k for k in STEP_KINDS if k in step]
    if len(kinds) != 1:
        return [f"step {sid}: it must be exactly one of run, gate or agent"]
    kind, problems = kinds[0], []
    if not isinstance(step[kind], str) or not step[kind]:
        return [f"step {sid}: {kind} must be a non-empty string"]
    if kind == "gate":
        gate = gates.get(step["gate"])
        if not isinstance(gate, dict):
            return problems + [f"step {sid}: no gate {step['gate']} in gates"]
        on = step.get("on")
        outcomes = gate.get("outcomes") or []
        if not isinstance(on, dict) or set(on) != set(outcomes):
            problems.append(f"step {sid}: on must map each of the gate's outcomes ({', '.join(outcomes)}) to a step")
        else:
            for outcome, target in on.items():
                if target != "end" and target not in ids:
                    problems.append(f"step {sid}: on {outcome} goes to {target}, which is not a step (or end)")
    if kind == "agent" and step.get("skill"):
        if not (folder / "skills" / str(step["skill"]) / "SKILL.md").exists():
            problems.append(f"step {sid}: there is no skills/{step['skill']}/SKILL.md")
    if "approval" in step and (not isinstance(step["approval"], str) or not step["approval"]):
        problems.append(f"step {sid}: approval must say what the person approves")
    return problems


def check_program(spec: Mapping[str, Any], program: ModuleType) -> List[str]:
    """Every function bot.json names that program.py does not have."""
    problems = []
    for step in spec.get("loop") or []:
        run = step.get("run") if isinstance(step, dict) else None
        if isinstance(run, str) and run and not callable(getattr(program, run, None)):
            problems.append(f"step {step.get('id')}: program.py has no function {run}")
    gates = spec.get("gates")
    for name, gate in (gates if isinstance(gates, dict) else {}).items():
        case = gate.get("case") if isinstance(gate, dict) else None
        if isinstance(case, str) and not callable(getattr(program, case, None)):
            problems.append(f"gate {name}: program.py has no function {case}")
    return problems
