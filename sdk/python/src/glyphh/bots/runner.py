"""The runner: a bot's program controls its Claude agent. The runner walks the bot's loop, runs its code steps itself,
asks Ada at its gates, and calls the agent (`claude -p`) only for the steps that need judgment, with the step's skill
and the bot's memory (its own, and the person's glyphh) put before it.

Gates learn: each is an Ada model of the bot's own. Under its confidence, or with no precedent yet, the person is
asked; their answer is recorded as a precedent, so the gate asks less run after run. A wrong call is corrected with
`wrong`, recorded the same way. Hard gates are code: a run step answering `{"_end": why}` ends the run, and a step
with an `approval` waits for the person's yes until the orchestrator trusts the bot to act alone."""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .. import __version__
from ..client import Ada, Model
from ..errors import AdaError, ModelMissingError
from .claude import Claude
from .memory import MEMORY_SPEC, memory_context, remember
from .package import KINDS, Bot, BotError

if TYPE_CHECKING:  # pragma: no cover
    from .orchestrator import Orchestrator

#: Sent with every request a bot's code makes (some hosts refuse urllib's own).
USER_AGENT = f"glyphh-bot/{__version__}"
#: Steps one run may take, gates looping back included, unless the bot's limits say `steps`.
MAX_STEPS = 200

Ask = Callable[[str, List[str]], str]
Fetch = Callable[[urllib.request.Request, float], Any]


class Stop(Exception):
    """The run stops here: `status` needs_input (with what it waits for, `pending`) or failed, with why."""

    def __init__(self, status: str, reason: str, pending: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(reason)
        self.status, self.reason, self.pending = status, reason, pending or {}


@dataclass
class RunResult:
    """How a run stands: `done` (`reason` says why it ended early, when it did), `needs_input` (`question`, one of
    `options` to answer with `continue`) or `failed` (`reason`)."""

    bot: str
    run_id: str
    status: str
    reason: str = ""
    question: Optional[str] = None
    options: Optional[List[str]] = None
    log: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        return {k: v for k, v in out.items() if v not in (None, "")}


class RunStore:
    """A bot's runs and state, in its folder's runs.sqlite."""

    def __init__(self, folder: Path) -> None:
        self.path = folder / "runs.sqlite"
        with self._db() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, started REAL, status TEXT, at INT, data TEXT,"
                " pending TEXT, reason TEXT, log TEXT)"
            )
            c.execute("CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT)")

    def _db(self) -> "closing[sqlite3.Connection]":
        return closing(sqlite3.connect(self.path, timeout=30))

    def save(
        self, run_id: str, status: str, at: int, data: Dict[str, Any], pending: Dict[str, Any], reason: str, log: List[str]
    ) -> None:
        with self._db() as c, c:
            c.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
                " at=excluded.at, data=excluded.data, pending=excluded.pending, reason=excluded.reason,"
                " log=excluded.log",
                (run_id, time.time(), status, at, json.dumps(data, default=str), json.dumps(pending), reason,
                 "\n".join(log)),
            )

    def _rows(self, where: str = "", args: tuple = (), limit: int = -1) -> List[Dict[str, Any]]:
        q = f"SELECT id, started, status, at, data, pending, reason, log FROM runs {where} ORDER BY started DESC LIMIT ?"
        with self._db() as c:
            rows = c.execute(q, (*args, limit)).fetchall()
        return [
            {"id": r[0], "started": r[1], "status": r[2], "at": r[3], "data": json.loads(r[4] or "{}"),
             "pending": json.loads(r[5] or "{}"), "reason": r[6] or "", "log": (r[7] or "").splitlines()}
            for r in rows
        ]

    def get(self, run_id: str) -> Optional[Dict[str, Any]]:
        found = self._rows("WHERE id = ?", (run_id,), 1)
        return found[0] if found else None

    def waiting(self) -> Optional[Dict[str, Any]]:
        """The newest run waiting for the person."""
        found = self._rows("WHERE status = 'needs_input'", (), 1)
        return found[0] if found else None

    def recent(self, limit: int = -1) -> List[Dict[str, Any]]:
        return self._rows(limit=limit)

    def state(self, k: str) -> Optional[str]:
        with self._db() as c:
            row = c.execute("SELECT v FROM state WHERE k = ?", (k,)).fetchone()
        return row[0] if row else None

    def set_state(self, k: str, v: str) -> None:
        with self._db() as c, c:
            c.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (k, v))


def _urlopen(req: urllib.request.Request, timeout: float) -> Any:
    with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310  only the bot's declared hosts
        return json.load(res)


class Ctx:
    """What a code step gets: `today`, `run_id`, `dir` (the bot's folder), `http_json` (GET JSON from the bot's hosts
    only), `db()` (the bot's own SQLite, data.sqlite), `state` and `set_state`, `gate(name)` (one of its gates' Ada
    models, for code that asks Ada itself), `log`. `home` is where bots live and `orchestrator` the orchestrator, for
    a bot that makes bots."""

    def __init__(self, runner: "Runner", run_id: str, log: List[str]) -> None:
        self._runner, self.run_id, self.lines = runner, run_id, log
        self.bot = runner.bot
        self.dir = runner.bot.dir
        self.home = runner.bot.dir.parent
        self.today: dt.date = runner.today()
        self.ada = runner.ada
        self.orchestrator = runner.orchestrator
        self._data: Optional[sqlite3.Connection] = None

    def http_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.bot.hosts:
            raise Stop("failed", f"{url} is not https on one of the bot's hosts ({', '.join(self.bot.hosts) or 'none'})")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
        return self._runner.fetch(req, 20.0)

    def db(self) -> sqlite3.Connection:
        if self._data is None:
            self._data = sqlite3.connect(self.dir / "data.sqlite", timeout=30)
        return self._data

    def state(self, k: str) -> Optional[str]:
        return self._runner.store.state(k)

    def set_state(self, k: str, v: str) -> None:
        self._runner.store.set_state(k, v)

    def gate(self, name: str) -> Model:
        if name not in self.bot.gates:
            raise Stop("failed", f"the bot has no gate {name}")
        return self.ada.model(self.bot.gate_model(name))

    def log(self, line: str) -> None:
        self.lines.append(line)
        self._runner.echo(line)

    def close(self) -> None:
        if self._data is not None:
            self._data.close()
            self._data = None


def fill(value: Any, data: Dict[str, Any]) -> Any:
    """`$id` in a step's input or prompt: an earlier step's data (the whole value, or as JSON inside a string)."""
    if isinstance(value, str) and re.fullmatch(r"\$\w+", value):
        return data.get(value[1:])
    if isinstance(value, str):
        return re.sub(
            r"\$(\w+)",
            lambda m: json.dumps(data.get(m.group(1)), default=str) if m.group(1) in data else m.group(0),
            value,
        )
    return value


def desktop_notify(title: str, text: str) -> None:
    """A notification on a Mac; elsewhere nothing (the run's result says it)."""
    if sys.platform == "darwin":
        script = f"display notification {json.dumps(text)} with title {json.dumps(title)}"
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def held(ada: Ada, name: str) -> int:
    """How many precedents an Ada model holds; 0 when it is not there."""
    try:
        return ada.model(name).info().precedents
    except ModelMissingError:
        return 0


def new_run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]


class Runner:
    """One bot, run. `ask` asks the person at the terminal (None: a question stops the run, `needs_input`); `echo`
    shows each log line as it happens; `notify` tells the person a routine run stopped."""

    def __init__(
        self,
        bot: Bot,
        ada: Ada,
        *,
        claude: Optional[Claude] = None,
        orchestrator: Optional["Orchestrator"] = None,
        ask: Optional[Ask] = None,
        echo: Optional[Callable[[str], None]] = None,
        notify: Optional[Callable[[str, str], None]] = None,
        fetch: Optional[Fetch] = None,
        today: Optional[Callable[[], dt.date]] = None,
    ) -> None:
        self.bot, self.ada = bot, ada
        self.claude = claude or Claude()
        self.orchestrator = orchestrator
        self.ask = ask
        self.echo = echo or (lambda line: None)
        self.notify = notify or desktop_notify
        self.fetch: Fetch = fetch or _urlopen
        self.today = today or dt.date.today
        self.store = RunStore(bot.dir)

    def trust(self) -> str:
        return self.orchestrator.trust_of(self.bot.slug) if self.orchestrator else "ask_all"

    # installing

    def install(self) -> Dict[str, Any]:
        """Make the bot's gate and memory models that are not there yet, and keep its seed lines."""
        have = {m.name for m in self.ada.models()}
        made = []
        for name, gate in self.bot.gates.items():
            model = self.bot.gate_model(name)
            if model not in have:
                self.ada.create_model(model, {**gate["spec"], "name": model})
                made.append(model)
        for kind in KINDS:
            model = self.bot.memory_model(kind)
            if model not in have:
                self.ada.create_model(model, {**MEMORY_SPEC, "name": model})
                made.append(model)
        seeded = 0
        for kind, lines in (self.bot.spec.get("seed") or {}).items():
            for line in lines:
                remember(self.ada, self.bot.memory_model(kind), kind, str(line), when="seed")
                seeded += 1
        return {"bot": self.bot.slug, "made": made, "seeded": seeded}

    # running

    def run(self, routine: bool = False) -> RunResult:
        """One run of the loop, from its first step. `routine`: nobody is watching, so a question stops the run."""
        if self.orchestrator and self.orchestrator.keep_of(self.bot.slug) == "retire":
            raise BotError(f"{self.bot.slug} is retired: the orchestrator's keep_bot (or the person) said so")
        run_id = new_run_id()
        self.echo(f"{self.bot.slug} run {run_id}{' (routine)' if routine else ''}")
        return self._walk(run_id, 0, {}, routine, None, [])

    def resume(self, answer: Optional[str] = None, routine: bool = False) -> RunResult:
        """Carry on the run that stopped for the person, with their answer (one of its options)."""
        row = self.store.waiting()
        if not row:
            raise BotError(f"{self.bot.slug}: no run is waiting for an answer")
        options = row["pending"].get("options") or []
        if answer is None and self.ask and not routine:
            answer = self._ask_here(row["pending"].get("question") or row["reason"], options)
        if answer is None:
            raise BotError(f"{self.bot.slug} run {row['id']} waits for an answer: one of {', '.join(options)}")
        if options and answer not in options:
            raise BotError(f"{answer} is not an answer to that: one of {', '.join(options)}")
        self.echo(f"{self.bot.slug} run {row['id']}: carrying on with {answer}")
        return self._walk(row["id"], row["at"], row["data"], routine, answer, row["log"], row["pending"])

    def _ask_here(self, question: str, options: List[str]) -> str:
        assert self.ask is not None
        while True:
            got = self.ask(question, options).strip().lower()
            if got in options:
                return got

    def _question(self, question: str, options: List[str], routine: bool, pending: Dict[str, Any]) -> str:
        if routine or self.ask is None:
            raise Stop("needs_input", question, {**pending, "question": question, "options": options})
        return self._ask_here(question, options)

    def _walk(
        self,
        run_id: str,
        at: int,
        data: Dict[str, Any],
        routine: bool,
        answer: Optional[str],
        log: List[str],
        pending_before: Optional[Dict[str, Any]] = None,
    ) -> RunResult:
        loop = self.bot.loop
        ids = [s["id"] for s in loop]
        ctx = Ctx(self, run_id, log)
        status, reason, pending = "done", "", {}
        budget = int(self.bot.limits.get("steps", MAX_STEPS))
        before = pending_before or {}
        try:
            while at < len(loop):
                budget -= 1
                if budget < 0:
                    raise Stop("failed", f"the run took more than {self.bot.limits.get('steps', MAX_STEPS)} steps")
                step = loop[at]
                if step.get("approval") and self.trust() != "autonomous" and not data.get("_approved", {}).get(step["id"]):
                    said = answer if answer is not None and before.get("approval") == step["id"] else None
                    if said is None:
                        said = self._question(
                            f"{step['id']}: {step['approval']}. Yes?", ["yes", "no"], routine, {"approval": step["id"]}
                        )
                    answer, before = None, {}
                    ctx.log(f"approval {step['approval']}: {said} (the person's)")
                    if said != "yes":
                        reason = f"the person said no to {step['approval']}"
                        break
                    data.setdefault("_approved", {})[step["id"]] = True
                if "run" in step:
                    ctx.log(f"run {step['run']}")
                    out = self._code(step["run"], ctx, fill(step.get("input"), data))
                    data[step["id"]] = out
                    if isinstance(out, dict) and out.get("_end"):
                        reason = f"the program ended the run: {out['_end']}"
                        ctx.log(reason)
                        break
                elif "gate" in step:
                    given = answer if before.get("gate") == step["gate"] else None
                    outcome = self._gate(ctx, step, data, routine, given, before)
                    answer, before = None, {}
                    data[step["id"]] = outcome
                    target = step["on"][outcome]
                    if target == "end":
                        reason = f"gate {step['gate']} said {outcome}: the run ends here"
                        ctx.log(reason)
                        break
                    data.get("_approved", {}).pop(step["id"], None)
                    at = ids.index(target)
                    self.store.save(run_id, "running", at, data, {}, "", log)
                    continue
                else:
                    data[step["id"]] = self._agent(ctx, step, data)
                data.get("_approved", {}).pop(step["id"], None)  # a yes is for this once
                at += 1
                self.store.save(run_id, "running", at, data, {}, "", log)
        except Stop as e:
            status, reason, pending = e.status, e.reason, e.pending
        finally:
            ctx.close()
        self.store.save(run_id, status, at, data, pending, reason, log)
        result = RunResult(
            self.bot.slug, run_id, status, reason, pending.get("question"), pending.get("options"), log, data
        )
        self._after(ctx, result, at, routine)
        return result

    def _code(self, function: str, ctx: Ctx, inputs: Any) -> Any:
        try:
            return getattr(self.bot.program, function)(ctx, inputs)
        except Stop:
            raise
        except Exception as e:  # noqa: BLE001  the bot's own code: whatever it raises fails the run, said plainly
            raise Stop("failed", f"{function}: {type(e).__name__}: {e}") from e

    def _gate(
        self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any], routine: bool, answer: Optional[str],
        pending: Dict[str, Any],
    ) -> str:
        name = step["gate"]
        gate = self.bot.gates[name]
        outcomes = list(gate["outcomes"])
        case = pending.get("case") if answer is not None and pending.get("case") else self._code(gate["case"], ctx, data)
        model_name = self.bot.gate_model(name)
        model = self.ada.model(model_name)
        n = held(self.ada, model_name)
        decision = model.decide(case) if n else None
        if answer is None and decision and not decision.ask and decision.outcome in outcomes:
            best = max(decision.probabilities.values()) if decision.probabilities else 0.0
            ctx.log(f"gate {name}: {decision.outcome} (P {best:.2f}, from {n} precedents), decided by Ada")
            data.setdefault("_gates", {})[name] = {"case": case, "outcome": decision.outcome, "by": "ada"}
            return str(decision.outcome)
        if answer is None:
            why = f"Ada's guess is {decision.outcome}, not sure enough" if decision else "no precedents yet"
            asked = gate.get("question") or f"Gate {name}"
            answer = self._question(
                f"{asked} ({why}). The case: {json.dumps(case, default=str)}. Which?",
                outcomes,
                routine,
                {"gate": name, "case": case, "guess": decision.outcome if decision else None},
            )
        model.record(case, answer)
        ctx.log(f"gate {name}: {answer}, the person's call, kept as precedent {n + 1}")
        data.setdefault("_gates", {})[name] = {"case": case, "outcome": answer, "by": "person"}
        return answer

    def _agent(self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any]) -> str:
        name, definition = self.bot.agent()
        prompt = str(fill(step["agent"], data))
        if step.get("skill"):
            prompt += f"\n\nHow to do it (your skill {step['skill']}):\n{self.bot.skill(step['skill'])}"
        known = memory_context(self.ada, self.bot, prompt[:1500])
        if known:
            prompt = f"{known}\n\n---\n\n{prompt}"
        ctx.log(f"agent {name}: {step['id']} ({len(prompt)} characters in, memory {'yes' if known else 'none yet'})")
        limits = self.bot.limits
        try:
            answer = self.claude.agent(
                name, definition, prompt, turns=int(limits.get("agent_turns", 3)), seconds=int(limits.get("seconds", 300))
            )
        except BotError as e:
            raise Stop("failed", f"{step['id']}: {e.message}") from e
        if step.get("remember"):
            remember(self.ada, self.bot.memory_model("memory"), "memory",
                     f"{ctx.today}: {step['id']}: {answer[:1500]}", when=f"run {ctx.run_id}")
        return answer

    def _after(self, ctx: Ctx, result: RunResult, at: int, routine: bool) -> None:
        """What is learned from every run: the orchestrator keeps it, the bot remembers how it ended; a routine run
        that did not finish tells the person."""
        loop = self.bot.loop
        where = f" at {loop[at]['id']}" if at < len(loop) else ""
        try:
            if self.orchestrator and result.status in ("done", "failed"):
                self.orchestrator.after_run(self.bot, result.run_id, result.status, result.data)
            remember(self.ada, self.bot.memory_model("memory"), "memory",
                     f"{ctx.today}: run {result.run_id} ended {result.status}{where}", when="run outcome")
        except AdaError as e:
            result.log.append(f"the run's outcome was not kept in memory: {e.message}")
        if result.status != "done" and routine:
            self.notify(self.bot.name, f"{result.status}{where}: glyphh bot continue {self.bot.slug}")

    # correcting and reading

    def wrong(self, run_id: str, outcome: str, gate: Optional[str] = None) -> Dict[str, Any]:
        """A gate decided that run wrong: record what it should have been, as a precedent."""
        row = self.store.get(run_id)
        if not row:
            raise BotError(f"{self.bot.slug}: no run {run_id}")
        gates = row["data"].get("_gates") or {}
        if not gates:
            raise BotError(f"{self.bot.slug} run {run_id} passed no gate: there is nothing to correct")
        if gate is None:
            if len(gates) > 1:
                raise BotError(f"run {run_id} passed several gates: say which ({', '.join(gates)})")
            gate = next(iter(gates))
        if gate not in gates:
            raise BotError(f"run {run_id} did not pass gate {gate} ({', '.join(gates)})")
        outcomes = self.bot.gates[gate]["outcomes"]
        if outcome not in outcomes:
            raise BotError(f"{outcome} is not one of gate {gate}'s outcomes ({', '.join(outcomes)})")
        g = gates[gate]
        self.ada.model(self.bot.gate_model(gate)).record(g["case"], outcome)
        if self.orchestrator:
            self.orchestrator.overruled(self.bot.slug, run_id)
        return {"bot": self.bot.slug, "run": run_id, "gate": gate, "said": g["outcome"], "by": g["by"], "now": outcome}

    def status(self, limit: int = 10) -> Dict[str, Any]:
        """Each gate's and memory's precedents, the bot's trust and keep, and its last runs."""
        have = {m.name: m.precedents for m in self.ada.models()}
        runs = []
        for r in self.store.recent(limit):
            gates = {n: f"{g['outcome']} by {g['by']}" for n, g in (r["data"].get("_gates") or {}).items()}
            runs.append({"run": r["id"], "status": r["status"], "gates": gates, "reason": r["reason"]})
        out: Dict[str, Any] = {
            "bot": self.bot.slug,
            "name": self.bot.name,
            "touches": self.bot.touches,
            "gates": {n: have.get(self.bot.gate_model(n), 0) for n in self.bot.gates},
            "memory": {k: have.get(self.bot.memory_model(k), 0) for k in KINDS},
            "runs": runs,
        }
        if self.orchestrator:
            out["trust"], out["keep"] = self.trust(), self.orchestrator.keep_of(self.bot.slug)
        return out
