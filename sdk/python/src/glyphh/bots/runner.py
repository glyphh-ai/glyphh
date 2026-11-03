"""The runner: a bot's program controls its Claude agent. The runner walks the bot's loop, runs its code steps itself,
asks Ada at its gates, and calls the agent (`claude -p`) only for the steps that need judgment, with the step's skill
and the bot's memory (its own, and the person's glyphh) put before it.

Learned gates are Ada models of the bot's own. A `gate` step decides one case, or with `each` every item of a list:
the items Ada is sure of are decided at once, the unsure ones asked as one batch (one by one at a terminal; in a
routine, or with no terminal, the run stops `needs_input` with the list, and `resume` takes the answers for all of
them). Each gate's policy (gates.py) says when Ada may decide alone. Every answer the person gives is recorded as a
precedent, so the gate asks less run after run; a wrong call is corrected with `wrong`, a world-answered gate's real
outcome recorded with `outcome`. A `ladder` step lets a gate pick the cheapest of ordered options it predicts will
work, escalates on a failed check and records what it took. An approval may name an `approval_gate` that learns the
person's yes and no; it still asks until both that gate is sure and the bot's trust allows.

Hard gates are code, never learned and never overridden: a run step answering `{"_end": why}` ends the run; bot.json's
`limits` cap spend (per run, per day), runs a day, quiet hours, items per list, steps and seconds; `requires` skips a
step or ends the run on a plain expression over earlier data; a paused bot does not run; code reaches only the bot's
hosts."""

from __future__ import annotations

import datetime as dt
import hashlib
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
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Tuple

from .. import __version__
from ..client import Ada
from ..errors import AdaError, ModelMissingError
from .claude import Claude
from .gates import Call, Gate, Policy
from .memory import MEMORY_SPEC, memory_context, remember
from .package import KINDS, OUTWARD, Bot, BotError
from .rules import REF, holds, json_answer, parse_answers, quiet, resolve, resolve_in, validate

if TYPE_CHECKING:  # pragma: no cover
    from .orchestrator import Orchestrator

#: Sent with every request a bot's code makes (some hosts refuse urllib's own).
USER_AGENT = f"glyphh-bot/{__version__}"
#: Steps one run may take, gates looping back included, unless the bot's limits say `steps`.
MAX_STEPS = 200
#: What may never act on its own unless the bot is trusted autonomous AND its approval gate is sure.
NEVER_ALONE = ("pays", "deletes")

Ask = Callable[[str, List[str]], str]
Fetch = Callable[[urllib.request.Request, float], Any]


class Stop(Exception):
    """The run stops here: `status` needs_input (with what it waits for, `pending`) or failed, with why."""

    def __init__(self, status: str, reason: str, pending: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(reason)
        self.status, self.reason, self.pending = status, reason, pending or {}


class End(Exception):
    """A hard gate ends the run here, done: `reason` says which."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class RunResult:
    """How a run stands: `done` (`reason` says why it ended early, when it did), `needs_input` (`question`, one of
    `options` to answer with `continue`; for a batch of items, `batch` lists them and `answer_with` shows how),
    `failed` (`reason`) or `skipped` (a hard limit kept it from starting: quiet hours, runs a day)."""

    bot: str
    run_id: str
    status: str
    reason: str = ""
    question: Optional[str] = None
    options: Optional[List[str]] = None
    batch: Optional[List[Dict[str, Any]]] = None
    answer_with: Optional[str] = None
    log: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        return {k: v for k, v in out.items() if v not in (None, "")}


DECISION_COLUMNS = ("run", "gate", "step", "n", "key", "label", "kind", "case_json", "outcome", "by", "p", "guess",
                    "mode", "agreed", "recorded", "world", "wrong", "day", "at")


class RunStore:
    """A bot's runs, state, gate decisions, spend and deferred items, in its folder's runs.sqlite."""

    def __init__(self, folder: Path) -> None:
        self.path = folder / "runs.sqlite"
        with self._db() as c, c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, started REAL, status TEXT, at INT, data TEXT,"
                " pending TEXT, reason TEXT, log TEXT)"
            )
            if "day" not in {r[1] for r in c.execute("PRAGMA table_info(runs)")}:
                c.execute("ALTER TABLE runs ADD COLUMN day TEXT")
            c.execute("CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT)")
            c.execute(
                "CREATE TABLE IF NOT EXISTS decisions (run TEXT, gate TEXT, step TEXT, n INT, key TEXT, label TEXT,"
                " kind TEXT, case_json TEXT, outcome TEXT, by TEXT, p REAL, guess TEXT, mode TEXT, agreed INT,"
                " recorded INT, world TEXT, wrong TEXT, day TEXT, at REAL, PRIMARY KEY (run, gate, step, n, key))"
            )
            c.execute("CREATE TABLE IF NOT EXISTS spend (run TEXT, day TEXT, usd REAL, what TEXT, at REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS deferred (gate TEXT, key TEXT, item TEXT, at REAL, PRIMARY KEY (gate, key))")

    def _db(self) -> "closing[sqlite3.Connection]":
        return closing(sqlite3.connect(self.path, timeout=30))

    # runs

    def save(
        self, run_id: str, status: str, at: int, data: Dict[str, Any], pending: Dict[str, Any], reason: str,
        log: List[str], day: Optional[str] = None,
    ) -> None:
        with self._db() as c, c:
            c.execute(
                "INSERT INTO runs (id, started, status, at, data, pending, reason, log, day) VALUES (?, ?, ?, ?, ?, ?, ?,"
                " ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, at=excluded.at, data=excluded.data,"
                " pending=excluded.pending, reason=excluded.reason, log=excluded.log",
                (run_id, time.time(), status, at, json.dumps(data, default=str), json.dumps(pending, default=str),
                 reason, "\n".join(log), day),
            )

    def _rows(self, where: str = "", args: tuple = (), limit: int = -1) -> List[Dict[str, Any]]:
        q = (f"SELECT id, started, status, at, data, pending, reason, log, day FROM runs {where} ORDER BY started DESC,"
             " rowid DESC LIMIT ?")
        with self._db() as c:
            rows = c.execute(q, (*args, limit)).fetchall()
        return [
            {"id": r[0], "started": r[1], "status": r[2], "at": r[3], "data": json.loads(r[4] or "{}"),
             "pending": json.loads(r[5] or "{}"), "reason": r[6] or "", "log": (r[7] or "").splitlines(), "day": r[8]}
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

    def runs_on(self, day: str) -> int:
        with self._db() as c:
            return int(c.execute("SELECT COUNT(*) FROM runs WHERE day = ?", (day,)).fetchone()[0])

    # state

    def state(self, k: str) -> Optional[str]:
        with self._db() as c:
            row = c.execute("SELECT v FROM state WHERE k = ?", (k,)).fetchone()
        return row[0] if row else None

    def set_state(self, k: str, v: Optional[str]) -> None:
        with self._db() as c, c:
            if v is None:
                c.execute("DELETE FROM state WHERE k = ?", (k,))
            else:
                c.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (k, v))

    # decisions

    def keep_decision(self, **row: Any) -> None:
        values = {k: row.get(k) for k in DECISION_COLUMNS}
        values["case_json"] = json.dumps(row.get("case"), default=str)
        values["key"] = "" if values["key"] is None else str(values["key"])
        values["at"] = time.time()
        for b in ("agreed", "recorded"):
            values[b] = None if values[b] is None else int(bool(values[b]))
        with self._db() as c, c:
            c.execute(
                f"INSERT OR REPLACE INTO decisions ({', '.join(DECISION_COLUMNS)}) VALUES "  # noqa: S608  fixed columns
                f"({', '.join('?' for _ in DECISION_COLUMNS)})",
                tuple(values[k] for k in DECISION_COLUMNS),
            )

    def decisions(self, run: Optional[str] = None, gate: Optional[str] = None) -> List[Dict[str, Any]]:
        where, args = [], []
        for col, v in (("run", run), ("gate", gate)):
            if v is not None:
                where.append(f"{col} = ?")
                args.append(v)
        q = (f"SELECT {', '.join(DECISION_COLUMNS)} FROM decisions {'WHERE ' + ' AND '.join(where) if where else ''}"  # noqa: S608
             " ORDER BY at, n")
        with self._db() as c:
            rows = c.execute(q, args).fetchall()
        out = []
        for r in rows:
            d = dict(zip(DECISION_COLUMNS, r))
            d["case"] = json.loads(d.pop("case_json") or "null")
            out.append(d)
        return out

    def mark(self, row: Mapping[str, Any], **changes: Any) -> None:
        sets = ", ".join(f"{k} = ?" for k in changes)
        with self._db() as c, c:
            c.execute(
                f"UPDATE decisions SET {sets} WHERE run = ? AND gate = ? AND step = ? AND n = ? AND key = ?",  # noqa: S608
                (*changes.values(), row["run"], row["gate"], row["step"], row["n"], row["key"]),
            )

    # spend

    def spend(self, run: str, day: str, usd: float, what: str) -> None:
        with self._db() as c, c:
            c.execute("INSERT INTO spend VALUES (?, ?, ?, ?, ?)", (run, day, float(usd), what, time.time()))

    def spent(self, run: Optional[str] = None, day: Optional[str] = None) -> float:
        col, v = ("run", run) if run is not None else ("day", day)
        with self._db() as c:
            got = c.execute(f"SELECT COALESCE(SUM(usd), 0) FROM spend WHERE {col} = ?", (v,)).fetchone()[0]  # noqa: S608
        return round(float(got), 6)

    def dearest_agent_step(self) -> float:
        with self._db() as c:
            return float(c.execute("SELECT COALESCE(MAX(usd), 0) FROM spend WHERE what LIKE 'agent %'").fetchone()[0])

    # items a per-item gate did not get to ask

    def deferred(self, gate: str) -> List[Tuple[str, Any]]:
        with self._db() as c:
            rows = c.execute("SELECT key, item FROM deferred WHERE gate = ? ORDER BY at", (gate,)).fetchall()
        return [(r[0], json.loads(r[1])) for r in rows]

    def set_deferred(self, gate: str, items: List[Tuple[str, Any]]) -> None:
        with self._db() as c, c:
            c.execute("DELETE FROM deferred WHERE gate = ?", (gate,))
            c.executemany("INSERT OR REPLACE INTO deferred VALUES (?, ?, ?, ?)",
                          [(gate, k, json.dumps(item, default=str), time.time() + i * 1e-6) for i, (k, item) in enumerate(items)])


def _urlopen(req: urllib.request.Request, timeout: float) -> Any:
    with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310  only the bot's declared hosts
        return json.load(res)


class Ctx:
    """What a code step gets: `today`, `run_id`, `dir` (the bot's folder), `data` (the run's data so far),
    `http_json` (GET JSON from the bot's hosts only), `db()` (the bot's own SQLite, data.sqlite), `state` and
    `set_state`, `gate(name)` (one of its gates, for code that asks or records itself), `spend(usd)` (money the step
    spent, counted against the bot's spend limits; answers what is left) and `budget()`, `log`. `home` is where bots
    live and `orchestrator` the orchestrator, for a bot that makes bots."""

    def __init__(self, runner: "Runner", run_id: str, log: List[str], data: Optional[Dict[str, Any]] = None) -> None:
        self._runner, self.run_id, self.lines = runner, run_id, log
        self.bot = runner.bot
        self.dir = runner.bot.dir
        self.home = runner.bot.dir.parent
        self.today: dt.date = runner.today()
        self.ada = runner.ada
        self.orchestrator = runner.orchestrator
        self.data: Dict[str, Any] = data if data is not None else {}
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

    def gate(self, name: str) -> Gate:
        if name not in self.bot.gates:
            raise Stop("failed", f"the bot has no gate {name}")
        return Gate(self, name)

    def spend(self, usd: float, what: str = "program") -> Optional[float]:
        """Money this step spent (an API's bill, a trial's cost): kept, and counted against `usd_per_run` and
        `usd_per_day`. Answers what is left (None when the bot has no spend limit)."""
        self._runner.store.spend(self.run_id, self.today.isoformat(), max(0.0, float(usd)), what)
        return self.budget()

    def budget(self) -> Optional[float]:
        """What is left to spend, the tighter of the run's and the day's limits; None when the bot has none."""
        return self._runner.budget_left(self.run_id)

    def log(self, line: str) -> None:
        self.lines.append(line)
        self._runner.echo(line)

    def close(self) -> None:
        if self._data is not None:
            self._data.close()
            self._data = None


def fill(value: Any, data: Dict[str, Any]) -> Any:
    """`$id` (or `$id.path`) in a step's input or prompt: an earlier step's data (the whole value, or as JSON inside a
    string). An id no step has made yet is left as written."""
    if isinstance(value, str) and REF.fullmatch(value):
        path = value[1:]
        return resolve(path, data) if path.split(".")[0] in data else None
    if isinstance(value, str):
        return REF.sub(
            lambda m: json.dumps(resolve(m.group(1), data), default=str) if m.group(1).split(".")[0] in data else m.group(0),
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


def _item_key(step: Mapping[str, Any], item: Any) -> str:
    if step.get("key"):
        found = resolve_in(item, step["key"])
        if found is not None:
            return str(found)
    if isinstance(item, Mapping) and item.get("id") is not None:
        return str(item["id"])
    return hashlib.sha256(json.dumps(item, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _item_label(step: Mapping[str, Any], item: Any) -> str:
    found = resolve_in(item, step.get("label")) if step.get("label") else None
    if found is None and isinstance(item, Mapping):
        found = item.get("title") or item.get("name")
    text = str(found) if found is not None else json.dumps(item, default=str)
    return text if len(text) <= 120 else text[:117] + "..."


def _p(p: Optional[float]) -> str:
    return f"P {p:.2f}" if p is not None else "no P"


class Runner:
    """One bot, run. `ask` asks the person at the terminal (None: a question stops the run, `needs_input`); `echo`
    shows each log line as it happens; `notify` tells the person a routine run stopped; `now` is the local time
    (quiet hours)."""

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
        now: Optional[Callable[[], dt.datetime]] = None,
    ) -> None:
        self.bot, self.ada = bot, ada
        self.claude = claude or Claude()
        self.orchestrator = orchestrator
        self.ask = ask
        self.echo = echo or (lambda line: None)
        self.notify = notify or desktop_notify
        self.fetch: Fetch = fetch or _urlopen
        self.today = today or dt.date.today
        self.now = now or dt.datetime.now
        self.store = RunStore(bot.dir)

    def trust(self) -> str:
        return self.orchestrator.trust_of(self.bot.slug) if self.orchestrator else "ask_all"

    # installing

    def install(self) -> Dict[str, Any]:
        """Make the bot's gate and memory models that are not there yet, and keep its seed lines. A gate's own
        `ask_below` is written into its spec's output too, so Ada's `ask` agrees with the policy."""
        have = {m.name for m in self.ada.models()}
        made = []
        for name, gate in self.bot.gates.items():
            model = self.bot.gate_model(name)
            if model not in have:
                spec = json.loads(json.dumps(gate["spec"]))
                if gate.get("ask_below") is not None:
                    spec.setdefault("output", {})["ask_below"] = gate["ask_below"]
                self.ada.create_model(model, {**spec, "name": model})
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

    # the kill switch

    def paused(self) -> Optional[str]:
        return self.store.state("_paused")

    def pause(self, why: str = "") -> Dict[str, Any]:
        """The kill switch: a paused bot refuses to run (its routine included) until `unpause`."""
        said = why or "paused by the person"
        self.store.set_state("_paused", f"{dt.datetime.now().isoformat(timespec='seconds')}: {said}")
        return {"bot": self.bot.slug, "paused": True, "why": said}

    def unpause(self) -> Dict[str, Any]:
        was = self.paused()
        self.store.set_state("_paused", None)
        return {"bot": self.bot.slug, "paused": False, "was": was}

    def _refuse(self) -> None:
        if self.orchestrator and self.orchestrator.keep_of(self.bot.slug) == "retire":
            raise BotError(f"{self.bot.slug} is retired: the orchestrator's keep_bot (or the person) said so")
        if self.paused():
            raise BotError(f"{self.bot.slug} is paused ({self.paused()}): `glyphh bot resume {self.bot.slug}` lets it run")

    # running

    def run(self, routine: bool = False) -> RunResult:
        """One run of the loop, from its first step. `routine`: nobody is watching, so a question stops the run."""
        self._refuse()
        limits = self.bot.limits
        day = self.today().isoformat()
        if routine and limits.get("quiet_hours") and quiet(str(limits["quiet_hours"]), self.now()):
            return RunResult(self.bot.slug, "", "skipped", f"quiet hours ({limits['quiet_hours']}): the routine run waits")
        if limits.get("runs_per_day") and self.store.runs_on(day) >= int(limits["runs_per_day"]):
            return RunResult(self.bot.slug, "", "skipped",
                             f"runs_per_day: {limits['runs_per_day']} runs today already, no more until tomorrow")
        run_id = new_run_id()
        self.store.save(run_id, "running", 0, {}, {}, "", [], day=day)
        self.echo(f"{self.bot.slug} run {run_id}{' (routine)' if routine else ''}")
        return self._walk(run_id, 0, {}, routine, None, [])

    def resume(self, answer: Any = None, routine: bool = False) -> RunResult:
        """Carry on the run that stopped for the person, with their answer: one of its options; for a batch of items,
        an answer for every one (`1=read 2=skip`, `rest=skip`, or a map)."""
        self._refuse()
        row = self.store.waiting()
        if not row:
            raise BotError(f"{self.bot.slug}: no run is waiting for an answer")
        pending = row["pending"]
        options = pending.get("options") or []
        if pending.get("batch"):
            numbers = [b["n"] for b in pending["batch"]]
            if answer is None and not (self.ask and not routine):
                raise BotError(f"{self.bot.slug} run {row['id']} waits for answers to {len(numbers)} items: "
                               f"{pending.get('answer_with') or 'N=outcome for each'}")
            if answer is not None:
                try:
                    answer = parse_answers(answer, numbers, options)
                except ValueError as e:
                    raise BotError(str(e)) from None
        else:
            if isinstance(answer, (list, tuple)):
                answer = " ".join(answer) if answer else None
            if answer is None and self.ask and not routine:
                answer = self._ask_here(pending.get("question") or row["reason"], options)
            if answer is None:
                raise BotError(f"{self.bot.slug} run {row['id']} waits for an answer: one of {', '.join(options)}")
            answer = str(answer).strip()
            if options and answer.lower() in options:
                answer = answer.lower()
            if options and answer not in options:
                raise BotError(f"{answer} is not an answer to that: one of {', '.join(options)}")
        self.echo(f"{self.bot.slug} run {row['id']}: carrying on with {self._said(answer)}")
        return self._walk(row["id"], row["at"], row["data"], routine, answer, row["log"], pending)

    @staticmethod
    def _said(answer: Any) -> str:
        if isinstance(answer, Mapping):
            return ", ".join(f"{k}={v}" for k, v in answer.items()) or "no answers"
        return "the answers asked here" if answer is None else str(answer)

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
        answer: Any,
        log: List[str],
        pending_before: Optional[Dict[str, Any]] = None,
    ) -> RunResult:
        loop = self.bot.loop
        ids = [s["id"] for s in loop]
        ctx = Ctx(self, run_id, log, data)
        status, reason, pending = "done", "", {}
        budget = int(self.bot.limits.get("steps", MAX_STEPS))
        before = pending_before or {}
        try:
            while at < len(loop):
                budget -= 1
                if budget < 0:
                    raise Stop("failed", f"the run took more than {self.bot.limits.get('steps', MAX_STEPS)} steps")
                step = loop[at]
                sid = step["id"]
                resumed = bool(before) and (
                    before.get("step") == sid if before.get("step")
                    else before.get("approval") == sid or (bool(before.get("gate")) and before.get("gate") == step.get("gate"))
                )
                given = answer if resumed else None
                if resumed:
                    answer = None
                mine = before if resumed else {}
                before = {} if resumed else before
                if step.get("requires") and not resumed and not holds(step["requires"], data):
                    if step.get("otherwise") == "end":
                        raise End(f"{sid} requires {step['requires']}: it does not hold, the run ends here")
                    ctx.log(f"skip {sid}: it requires {step['requires']}, which does not hold")
                    data[sid] = None
                    at += 1
                    continue
                self._spend_gate(run_id, self.store.dearest_agent_step() if "agent" in step else 0.0, sid)
                if step.get("approval"):
                    refused = self._approval(ctx, step, data, routine, given if mine.get("approval") == sid else None, mine)
                    if refused:
                        reason = refused
                        break
                    if mine.get("approval") == sid:
                        given, mine = None, {}
                if "run" in step:
                    ctx.log(f"run {step['run']}")
                    out = self._code(step["run"], ctx, fill(step.get("input"), data))
                    data[sid] = out
                    if isinstance(out, dict) and out.get("_end"):
                        reason = f"the program ended the run: {out['_end']}"
                        ctx.log(reason)
                        break
                elif "gate" in step and step.get("each"):
                    out = self._each(ctx, step, data, routine, given if mine.get("each") == sid else None)
                    data[sid] = out
                    target = self._route_each(step, out)
                    if target == "end":
                        reason = f"gate {step['gate']}: {self._each_summary(out, step)}; the run ends here"
                        ctx.log(reason)
                        break
                    if target:
                        data.get("_approved", {}).pop(sid, None)
                        at = ids.index(target)
                        self.store.save(run_id, "running", at, data, {}, "", log)
                        continue
                elif "gate" in step:
                    outcome = self._gate(ctx, step, data, routine, given if mine.get("gate") == step["gate"] else None, mine)
                    data[sid] = outcome
                    target = step["on"][outcome]
                    if target == "end":
                        reason = f"gate {step['gate']} said {outcome}: the run ends here"
                        ctx.log(reason)
                        break
                    data.get("_approved", {}).pop(sid, None)
                    at = ids.index(target)
                    self.store.save(run_id, "running", at, data, {}, "", log)
                    continue
                elif "ladder" in step:
                    data[sid] = self._ladder(ctx, step, data)
                else:
                    data[sid] = self._agent(ctx, step, data)
                data.get("_approved", {}).pop(sid, None)  # a yes is for this once
                at += 1
                self.store.save(run_id, "running", at, data, {}, "", log)
        except End as e:
            reason = e.reason
            ctx.log(reason)
        except Stop as e:
            status, reason, pending = e.status, e.reason, e.pending
        finally:
            ctx.close()
        self.store.save(run_id, status, at, data, pending, reason, log)
        result = RunResult(
            self.bot.slug, run_id, status, reason, pending.get("question"), pending.get("options"), pending.get("batch"),
            pending.get("answer_with"), log, data,
        )
        self._after(ctx, result, at, routine)
        return result

    def _code(self, function: str, ctx: Ctx, *inputs: Any) -> Any:
        try:
            return getattr(self.bot.program, function)(ctx, *inputs)
        except (Stop, End):
            raise
        except Exception as e:  # noqa: BLE001  the bot's own code: whatever it raises fails the run, said plainly
            raise Stop("failed", f"{function}: {type(e).__name__}: {e}") from e

    # spend, a hard gate

    def budget_left(self, run_id: str) -> Optional[float]:
        limits = self.bot.limits
        left = []
        if limits.get("usd_per_run") is not None:
            left.append(float(limits["usd_per_run"]) - self.store.spent(run=run_id))
        if limits.get("usd_per_day") is not None:
            left.append(float(limits["usd_per_day"]) - self.store.spent(day=self.today().isoformat()))
        return round(max(0.0, min(left)), 6) if left else None

    def _spend_gate(self, run_id: str, estimate: float, what: str) -> None:
        """End the run before a step that would pass a spend limit (an agent step is judged by the dearest one yet)."""
        limits = self.bot.limits
        for key, spent in (("usd_per_run", lambda: self.store.spent(run=run_id)),
                           ("usd_per_day", lambda: self.store.spent(day=self.today().isoformat()))):
            if limits.get(key) is None:
                continue
            cap, got = float(limits[key]), spent()
            if got >= cap or (estimate > 0 and got + estimate > cap):
                more = f"; {what} (about ${estimate:.2f}) would pass it" if got < cap else ""
                raise End(f"spend: ${got:.2f} of {key} ${cap:.2f} spent{more}: the run ends here")

    # learned gates

    def _judge(self, name: str, case: Dict[str, Any], seed: str, n: Optional[int] = None) -> Call:
        gate = self.bot.gates[name]
        model_name = self.bot.gate_model(name)
        n = held(self.ada, model_name) if n is None else n
        decision = self.ada.model(model_name).decide(case) if n else None
        return Policy.of(name, gate).judge(decision, n, seed)

    def _keep(self, ctx: Ctx, **row: Any) -> None:
        self.store.keep_decision(run=ctx.run_id, day=ctx.today.isoformat(), **row)

    def _gate(
        self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any], routine: bool, answer: Optional[str],
        pending: Dict[str, Any],
    ) -> str:
        name = step["gate"]
        gate = self.bot.gates[name]
        policy = Policy.of(name, gate)
        outcomes = list(gate["outcomes"])
        case = pending.get("case") if answer is not None and pending.get("case") is not None else self._code(gate["case"], ctx, data)
        model_name = self.bot.gate_model(name)
        row = {"gate": name, "step": step["id"], "n": 0, "key": "", "label": "", "kind": "gate", "case": case}
        if answer is None:
            n = held(self.ada, model_name)
            call = self._judge(name, case, f"{ctx.run_id}:{name}", n)
            if not call.ask:
                ctx.log(f"gate {name}: {call.outcome} ({_p(call.p)}, from {n} precedents), decided by Ada")
                data.setdefault("_gates", {})[name] = {"case": case, "outcome": call.outcome, "by": "ada", "p": call.p}
                self._keep(ctx, **row, outcome=call.outcome, by="ada", p=call.p, guess=call.outcome, mode="ada",
                           recorded=False)
                return str(call.outcome)
            asked_n = data.setdefault("_asked", {}).get(name, 0)
            if policy.max_questions is not None and asked_n >= policy.max_questions:
                if policy.default:
                    ctx.log(f"gate {name}: {policy.default}, its default (no questions left this run; not kept)")
                    data.setdefault("_gates", {})[name] = {"case": case, "outcome": policy.default, "by": "default"}
                    self._keep(ctx, **row, outcome=policy.default, by="default", p=call.p, guess=call.outcome,
                               mode=call.mode, recorded=False)
                    return policy.default
                raise End(f"gate {name}: no questions left this run (max_questions {policy.max_questions}); it waits"
                          " for the next run")
            data["_asked"][name] = asked_n + 1
            asked = gate.get("question") or f"Gate {name}"
            answer = self._question(
                f"{asked} ({call.why}). The case: {json.dumps(case, default=str)}. Which?",
                outcomes,
                routine,
                {"step": step["id"], "gate": name, "case": case, "guess": call.outcome, "mode": call.mode, "p": call.p},
            )
            guess, mode, p = call.outcome, call.mode, call.p
        else:
            guess, mode, p = pending.get("guess"), pending.get("mode"), pending.get("p")
        if policy.world:
            ctx.log(f"gate {name}: {answer}, the person's call for now; the world's outcome is recorded later")
        else:
            n = held(self.ada, model_name)
            self.ada.model(model_name).record(case, answer)
            ctx.log(f"gate {name}: {answer}, the person's call, kept as precedent {n + 1}")
        data.setdefault("_gates", {})[name] = {"case": case, "outcome": answer, "by": "person"}
        self._keep(ctx, **row, outcome=answer, by="person", p=p, guess=guess, mode=mode,
                   agreed=None if guess is None else guess == answer, recorded=not policy.world)
        return answer

    def _each(
        self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any], routine: bool, answers: Optional[Dict[int, str]],
    ) -> Dict[str, Any]:
        """A gate on every item of a list: Ada's sure calls at once, the rest asked as one batch."""
        sid, name = step["id"], step["gate"]
        gate = self.bot.gates[name]
        policy = Policy.of(name, gate)
        outcomes = list(gate["outcomes"])
        model_name = self.bot.gate_model(name)
        state = data.setdefault("_each", {}).get(sid)
        if state is None:
            state = self._each_start(ctx, step, data, policy)
            data["_each"][sid] = state
        entries = state["entries"]
        asking = [e for e in entries if e["by"] == "asking"]
        if asking and answers is None:
            question = gate.get("question") or f"Gate {name}"
            if self.ask is not None and not routine:
                answers = {}
                for i, e in enumerate(asking, 1):
                    answers[e["n"]] = self._ask_here(f"{question} [{i}/{len(asking)}] {e['label']} ({e['why']})", outcomes)
            else:
                example = " ".join(f"{e['n']}={outcomes[i % len(outcomes)]}" for i, e in enumerate(asking[:2]))
                answer_with = f"glyphh bot continue {self.bot.slug} {example}{' rest=' + outcomes[-1] if len(asking) > 2 else ''}"
                lines = "\n".join(f"  {e['n']}. {e['label']} ({e['why']})" for e in asking)
                said = f"{question} {len(asking)} to answer ({', '.join(outcomes)}):\n{lines}"
                batch = [{"n": e["n"], "label": e["label"], "guess": e["guess"], "p": e["p"], "why": e["why"]} for e in asking]
                raise Stop("needs_input", said, {"step": sid, "each": sid, "gate": name, "question": said,
                                                 "options": outcomes, "batch": batch, "answer_with": answer_with})
        n = held(self.ada, model_name) if asking else 0
        for e in asking:
            got = answers[e["n"]] if answers else None
            if got not in outcomes:
                raise Stop("failed", f"{sid}: item {e['n']} has no answer")
            e["outcome"], e["by"] = got, "person"
            e["agreed"] = None if e["guess"] is None else e["guess"] == got
            if not policy.world:
                self.ada.model(model_name).record(e["case"], got)
                n += 1
        if asking:
            ctx.log(f"gate {name}: {len(asking)} answered by the person{'' if policy.world else f', kept (now {n} precedents)'}")
        return self._each_finish(ctx, step, data, policy, state)

    def _each_start(self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any], policy: Policy) -> Dict[str, Any]:
        sid, name = step["id"], step["gate"]
        gate = self.bot.gates[name]
        items = fill(step["each"], data)
        if items is None:
            items = []
        if not isinstance(items, list):
            raise Stop("failed", f"{sid}: each {step['each']} is not a list")
        keyed: List[Tuple[str, Any]] = []
        seen = set()
        for key, item in self.store.deferred(name) + [(_item_key(step, it), it) for it in items]:
            if key not in seen:
                seen.add(key)
                keyed.append((key, item))
        cap = step.get("max_items") or self.bot.limits.get("max_items")
        dropped = 0
        if cap and len(keyed) > int(cap):
            dropped = len(keyed) - int(cap)
            keyed = keyed[: int(cap)]
            ctx.log(f"gate {name}: max_items {cap}, {dropped} items dropped")
        model_name = self.bot.gate_model(name)
        n = held(self.ada, model_name)
        model = self.ada.model(model_name)
        left = policy.max_questions
        entries = []
        for i, (key, item) in enumerate(keyed, 1):
            case = self._code(gate["case"], ctx, item)
            call = policy.judge(model.decide(case) if n else None, n, f"{ctx.run_id}:{name}:{key}")
            e = {"n": i, "key": key, "label": _item_label(step, item), "item": item, "case": case, "outcome": None,
                 "by": None, "p": call.p, "guess": call.outcome, "mode": call.mode, "why": call.why, "agreed": None}
            if not call.ask:
                e["outcome"], e["by"] = call.outcome, "ada"
            elif left is not None and left <= 0:
                if policy.default:
                    e["outcome"], e["by"] = policy.default, "default"
                else:
                    e["by"] = "deferred"
            else:
                e["by"] = "asking"
                left = None if left is None else left - 1
            entries.append(e)
        sure = sum(1 for e in entries if e["by"] == "ada")
        ctx.log(f"gate {name}: {len(entries)} items; Ada decided {sure}, {sum(1 for e in entries if e['by'] == 'asking')}"
                f" to ask the person ({n} precedents)")
        return {"entries": entries, "dropped": dropped}

    def _each_finish(self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any], policy: Policy,
                     state: Dict[str, Any]) -> Dict[str, Any]:
        sid, name = step["id"], step["gate"]
        entries = state["entries"]
        done = [e for e in entries if e["by"] != "deferred"]
        out: Dict[str, Any] = {o: [e["item"] for e in done if e["outcome"] == o] for o in policy.outcomes}
        out["decisions"] = [{k: e[k] for k in ("n", "key", "label", "outcome", "by", "p", "guess", "mode", "agreed")}
                            for e in entries]
        count = {b: sum(1 for e in entries if e["by"] == b) for b in ("person", "ada", "default", "deferred")}
        out.update({"asked": count["person"], "decided": count["ada"], "defaulted": count["default"],
                    "deferred": count["deferred"], "dropped": state.get("dropped", 0)})
        self.store.set_deferred(name, [(e["key"], e["item"]) for e in entries if e["by"] == "deferred"])
        for e in entries:
            if e["by"] == "deferred":
                continue
            self._keep(ctx, gate=name, step=sid, n=e["n"], key=e["key"], label=e["label"], kind="each", case=e["case"],
                       outcome=e["outcome"], by=e["by"], p=e["p"], guess=e["guess"], mode=e["mode"],
                       agreed=e["agreed"], recorded=e["by"] == "person" and not policy.world)
        data.get("_each", {}).pop(sid, None)
        summary = ", ".join(f"{o} {len(out[o])}" for o in policy.outcomes)
        data.setdefault("_gates", {})[name] = {"each": True, "outcome": summary, "by": "person" if count["person"] else "ada",
                                               "asked": count["person"], "decided": count["ada"],
                                               "defaulted": count["default"]}
        if count["deferred"]:
            ctx.log(f"gate {name}: {count['deferred']} not asked this run (max_questions); they wait for the next")
        ctx.log(f"gate {name}: {summary} (Ada {count['ada']}, the person {count['person']}, default {count['default']})")
        return out

    @staticmethod
    def _each_summary(out: Mapping[str, Any], step: Mapping[str, Any]) -> str:
        return ", ".join(f"{k} {len(v)}" for k, v in out.items() if isinstance(v, list) and k != "decisions")

    @staticmethod
    def _route_each(step: Mapping[str, Any], out: Mapping[str, Any]) -> Optional[str]:
        """`on` after a per-item gate, its rules in order: `empty:<o>`, `any:<o>`, `all:<o>`, `else`."""
        for rule, target in (step.get("on") or {}).items():
            kind, _, o = rule.partition(":")
            got = out.get(o) or []
            decided = sum(len(v) for k, v in out.items() if isinstance(v, list) and k != "decisions")
            if (kind == "empty" and not got) or (kind == "any" and got) or (kind == "else") or \
               (kind == "all" and got and len(got) == decided):
                return str(target)
        return None

    # approvals

    def _approval(
        self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any], routine: bool, said: Optional[str],
        pending: Dict[str, Any],
    ) -> Optional[str]:
        """The person's yes before a step that acts; None to go on, else why the run ends. Trust decides who is
        asked: ask_all, every approval; ask_outward, the outward ones (sends, pays, deletes); autonomous, none, but
        never pays or deletes alone. An `approval_gate` learns the person's yes and no: it may stand in only when both
        it is sure and trust allows, and every answer the person gives it is kept."""
        sid = step["id"]
        if data.get("_approved", {}).get(sid):
            return None
        trust = self.trust()
        touches = str(step.get("touches") or self.bot.touches)
        outward = touches in OUTWARD
        allows = trust == "autonomous" or (trust == "ask_outward" and not outward)
        name = step.get("approval_gate")
        call: Optional[Call] = None
        case = None
        if name:
            gate = self.bot.gates[name]
            case = pending.get("case") if said is not None and pending.get("case") is not None else self._code(gate["case"], ctx, data)
            if said is None:
                call = self._judge(name, case, f"{ctx.run_id}:{name}:{sid}")
                if allows and not call.ask:
                    ctx.log(f"approval {step['approval']}: {call.outcome} by its approval gate {name} ({_p(call.p)}), trust {trust}")
                    self._keep(ctx, gate=name, step=sid, n=0, key="", label=step["approval"], kind="approval", case=case,
                               outcome=call.outcome, by="ada", p=call.p, guess=call.outcome, mode="ada", recorded=False)
                    if call.outcome != "yes":
                        return f"approval gate {name} said no to {step['approval']}"
                    data.setdefault("_approved", {})[sid] = True
                    return None
        elif said is None and allows and touches not in NEVER_ALONE:
            return None
        if said is None:
            why = f" ({call.why})" if call else ""
            said = self._question(
                f"{sid}: {step['approval']}. Yes?{why}", ["yes", "no"], routine,
                {"step": sid, "approval": sid, "case": case, "guess": call.outcome if call else None,
                 "mode": call.mode if call else None, "p": call.p if call else None},
            )
            guess, mode, p = (call.outcome, call.mode, call.p) if call else (None, None, None)
        else:
            guess, mode, p = pending.get("guess"), pending.get("mode"), pending.get("p")
        if name:
            self.ada.model(self.bot.gate_model(name)).record(case, said)
            self._keep(ctx, gate=name, step=sid, n=0, key="", label=step["approval"], kind="approval", case=case,
                       outcome=said, by="person", p=p, guess=guess, mode=mode,
                       agreed=None if guess is None else guess == said, recorded=True)
        ctx.log(f"approval {step['approval']}: {said} (the person's)")
        if said != "yes":
            return f"the person said no to {step['approval']}"
        data.setdefault("_approved", {})[sid] = True
        return None

    # the ladder

    def _ladder(self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Ordered options, cheapest first: the gate picks the cheapest it predicts will work, `try` does it, `check`
        says whether it worked, a failure goes one up; what it took is recorded (the world's answer, not a guess)."""
        if step.get("each"):
            items = fill(step["each"], data)
            if not isinstance(items, list):
                raise Stop("failed", f"{step['id']}: each {step['each']} is not a list")
            cap = step.get("max_items") or self.bot.limits.get("max_items")
            items = items[: int(cap)] if cap else items
            done = [self._climb(ctx, step, item, i) for i, item in enumerate(items, 1)]
            return {"items": done, "ok": sum(1 for d in done if d["ok"]), "failed": sum(1 for d in done if not d["ok"])}
        return self._climb(ctx, step, fill(step.get("input"), data), 0)

    def _climb(self, ctx: Ctx, step: Dict[str, Any], item: Any, n: int) -> Dict[str, Any]:
        name = step["ladder"]
        gate = self.bot.gates[name]
        rungs = list(gate["outcomes"])
        policy = Policy.of(name, gate)
        key = _item_key(step, item) if n else ""
        case = self._code(gate["case"], ctx, item)
        call = self._judge(name, case, f"{ctx.run_id}:{name}:{key}")
        start = step.get("start") or policy.default or rungs[0]
        start, by = (call.outcome, "ada") if call.sure and call.outcome in rungs else (start, "default")
        tried, won, result = [], None, None
        for rung in rungs[rungs.index(start):]:
            self._spend_gate(ctx.run_id, 0.0, f"{step['id']} {rung}")
            result = self._code(step["try"], ctx, rung, item)
            ok = self._code(step["check"], ctx, rung, result, item)
            tried.append({"rung": rung, "ok": bool(ok)})
            ctx.log(f"ladder {name}: {rung} {'worked' if ok else 'did not work'}")
            if ok:
                won = rung
                break
        if won:
            self.ada.model(self.bot.gate_model(name)).record(case, won)
        label = _item_label(step, item) if n else step["id"]
        self._keep(ctx, gate=name, step=step["id"], n=n, key=key, label=label, kind="ladder", case=case, outcome=start,
                   by=by, p=call.p, guess=call.outcome, mode=call.mode, recorded=bool(won), world=won,
                   agreed=None if won is None else won == start)
        out = {"rung": won, "start": start, "by": by, "p": call.p, "tried": tried, "ok": won is not None, "result": result}
        if n:
            out.update({"n": n, "label": label})
        if won is None:
            fail = step.get("on_fail", "next")
            why = f"{step['id']}: no rung of {name} worked ({', '.join(t['rung'] for t in tried)})"
            if fail == "fail":
                raise Stop("failed", why)
            if fail == "end":
                raise End(f"{why}: the run ends here")
            ctx.log(why)
        return out

    # Claude

    def _agent(self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any]) -> Any:
        name, definition = self.bot.agent()
        prompt = str(fill(step["agent"], data))
        if step.get("skill"):
            prompt += f"\n\nHow to do it (your skill {step['skill']}):\n{self.bot.skill(step['skill'])}"
        if step.get("schema"):
            prompt += ("\n\nAnswer with JSON only, nothing before or after it, fitting this JSON Schema:\n"
                       + json.dumps(step["schema"]))
        known = memory_context(self.ada, self.bot, prompt[:1500])
        if known:
            prompt = f"{known}\n\n---\n\n{prompt}"
        ctx.log(f"agent {name}: {step['id']} ({len(prompt)} characters in, memory {'yes' if known else 'none yet'})")
        limits = self.bot.limits
        value: Any = None
        text = ""
        for attempt in (1, 2):
            try:
                got = self.claude.answer(
                    name, definition, prompt, turns=int(limits.get("agent_turns", 3)), seconds=int(limits.get("seconds", 300))
                )
            except BotError as e:
                raise Stop("failed", f"{step['id']}: {e.message}") from e
            if got.cost_usd:
                self.store.spend(ctx.run_id, ctx.today.isoformat(), got.cost_usd, f"agent {step['id']}")
            problems = self._answer_problems(ctx, step, data, got.text)
            if not problems[0]:
                value = problems[1]
                text = got.text
                break
            if attempt == 2:
                raise Stop("failed", f"{step['id']}: the agent's answer is still not right: {problems[0]}")
            ctx.log(f"agent {name}: {step['id']}'s answer is not right ({problems[0]}): asked once more")
            self._spend_gate(ctx.run_id, self.store.dearest_agent_step(), f"{step['id']} again")
            prompt += f"\n\nYour answer was not right: {problems[0]}. Answer again, only what is asked."
        if step.get("remember"):
            remember(self.ada, self.bot.memory_model("memory"), "memory",
                     f"{ctx.today}: {step['id']}: {text[:1500]}", when=f"run {ctx.run_id}")
        return value

    def _answer_problems(self, ctx: Ctx, step: Dict[str, Any], data: Dict[str, Any], text: str) -> Tuple[str, Any]:
        """('', the answer's value) when the agent's answer is right; else (what is wrong, None)."""
        value: Any = text
        if step.get("schema"):
            try:
                value = json_answer(text)
            except ValueError:
                return "it is not JSON", None
            bad = validate(value, step["schema"])
            if bad:
                return "; ".join(bad[:5]), None
        if step.get("check"):
            verdict = self._code(step["check"], ctx, value, data)
            if verdict is False or isinstance(verdict, str):
                return verdict or f"{step['check']} said no", None
        return "", value

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

    # correcting, the world's answers, reading

    def _run_row(self, run_id: str) -> Dict[str, Any]:
        row = self.store.recent(1)[0] if run_id == "last" and self.store.recent(1) else self.store.get(run_id)
        if not row:
            raise BotError(f"{self.bot.slug}: no run {run_id}")
        return row

    def _find(self, run_id: str, gate: str, item: Optional[str]) -> Dict[str, Any]:
        rows = [r for r in self.store.decisions(run=run_id, gate=gate) if r["kind"] != "code" or item is not None]
        if item is not None:
            rows = [r for r in rows if (item.isdigit() and r["n"] == int(item)) or r["key"] == item]
        if not rows:
            raise BotError(f"run {run_id} has no case of gate {gate}{f' for item {item}' if item else ''}")
        if len(rows) > 1:
            raise BotError(f"run {run_id} decided {len(rows)} cases at gate {gate}: say which item (its number or key)")
        return rows[0]

    def wrong(self, run_id: str, outcome: str, gate: Optional[str] = None, item: Optional[str] = None) -> Dict[str, Any]:
        """A gate decided that run (or one item of it) wrong: record what it should have been, as a precedent."""
        row = self._run_row(run_id)
        run_id = row["id"]
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
        if g.get("each") or item is not None:
            if item is None:
                raise BotError(f"gate {gate} decided many items in run {run_id}: say which (--item N)")
            d = self._find(run_id, gate, item)
            self.ada.model(self.bot.gate_model(gate)).record(d["case"], outcome)
            self.store.mark(d, wrong=outcome, recorded=1)
            said, by = d["outcome"], d["by"]
        else:
            self.ada.model(self.bot.gate_model(gate)).record(g["case"], outcome)
            for d in self.store.decisions(run=run_id, gate=gate):
                self.store.mark(d, wrong=outcome, recorded=1)
            said, by = g["outcome"], g["by"]
        if self.orchestrator:
            self.orchestrator.overruled(self.bot.slug, run_id)
        out = {"bot": self.bot.slug, "run": run_id, "gate": gate, "said": said, "by": by, "now": outcome}
        return {**out, "item": item} if item is not None else out

    def outcome(self, run_id: str, gate: str, item: Optional[str], outcome: str) -> Dict[str, Any]:
        """What really happened to a case a gate decided (a world-answered gate's outcome): recorded as a precedent;
        where Ada had decided otherwise it counts as an overrule."""
        if gate not in self.bot.gates:
            raise BotError(f"{self.bot.slug} has no gate {gate} ({', '.join(self.bot.gates)})")
        outcomes = self.bot.gates[gate]["outcomes"]
        if outcome not in outcomes:
            raise BotError(f"{outcome} is not one of gate {gate}'s outcomes ({', '.join(outcomes)})")
        run_id = self._run_row(run_id)["id"] if run_id == "last" else run_id
        d = self._find(run_id, gate, item)
        self.ada.model(self.bot.gate_model(gate)).record(d["case"], outcome)
        self.store.mark(d, world=outcome, recorded=1)
        overruled = d["by"] == "ada" and d["outcome"] != outcome
        if overruled and self.orchestrator:
            self.orchestrator.overruled(self.bot.slug, run_id)
        return {"bot": self.bot.slug, "run": run_id, "gate": gate, "item": d["key"] or None, "decided": d["outcome"],
                "by": d["by"], "outcome": outcome, "overruled": overruled}

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
        if self.paused():
            out["paused"] = self.paused()
        if self.orchestrator:
            out["trust"], out["keep"] = self.trust(), self.orchestrator.keep_of(self.bot.slug)
        return out

    def gates(self, runs: int = 10) -> Dict[str, Any]:
        from .report import gate_stats

        return gate_stats(self, runs)

    def report(self, runs: int = 30) -> Dict[str, Any]:
        from .report import write_report

        return write_report(self, runs)
