"""The orchestrator: the Claude that makes bots, and learns how to make them.

It has its own memory and three Ada gates of its own, each learning only from the person's verdicts and the bots'
real records, never from its own guesses:

  make_bot   should this job become a bot (make / not_yet / no)
  trust_bot  how far a bot may act without asking (autonomous / ask_outward / ask_all)
  keep_bot   keep, fix or retire a bot, from its record

Every bot it makes gets gates of its own (the runner's). Every bot run is kept in the orchestrator's memory, so when
it builds the next bot, its builder agent starts from what worked for the bots before. The bots learn their jobs; the
orchestrator learns to build bots. Its trust and keep calls are kept in orchestrator.sqlite beside the bots."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from ..client import Ada
from .claude import Claude
from .memory import MEMORY_SPEC, recall, remember
from .package import KINDS, TOUCHES, Bot, BotError, bots_root, model_name
from .runner import Ask, Fetch, Runner, RunStore, held

HERE = Path(__file__).resolve().parent
#: The package format the builder follows, and the bot it is shown as an example.
BUILDING = HERE / "BUILDING.md"
EXAMPLE = HERE / "example"
EXAMPLE_ITEMS = HERE / "example_items"
TRUST = ("autonomous", "ask_outward", "ask_all")
KEEP = ("keep", "fix", "retire")
OUTCOMES = {"make_bot": ["make", "not_yet", "no"], "trust_bot": list(TRUST), "keep_bot": list(KEEP)}
#: What the orchestrator tells itself first, and never forgets.
FIRST_RULE = (
    "Never let a bot act outward (send, post, pay, delete) without the person's yes until trust_bot and the person "
    "agree it may."
)
STOPWORDS = {"a", "an", "the", "and", "of", "to", "for", "my", "me", "every", "each", "in", "on", "at", "it"}
COPY_SKIP = shutil.ignore_patterns("runs.sqlite", "data.sqlite", "__pycache__", "*.pyc", "routine.log",
                                   "report.html")


def _text_spec(extra: List[Dict[str, Any]], costs: Dict[str, Dict[str, float]], ask_below: float) -> Dict[str, Any]:
    roles = [{"name": "text", "text_encoding": "bag_of_words"}, {"name": "touches"}, *extra,
             {"name": "key", "key_part": True, "similarity_weight": 0}]
    return {"layers": [{"name": "o", "segments": [{"name": "s", "roles": roles}]}],
            "output": {"costs": costs, "ask_below": ask_below}}


def _num(name: str, high: int, step: int) -> Dict[str, Any]:
    return {"name": name, "numeric_config": {"min_value": 0, "max_value": high, "bin_width": step}}


#: The orchestrator's own gates, as Ada specs.
GATES: Dict[str, Dict[str, Any]] = {
    "make_bot": _text_spec(
        [_num("recurs_per_week", 50, 1), _num("similar_bots", 20, 1)],
        {"make": {"no": 5, "not_yet": 1}, "not_yet": {"make": 1}, "no": {"make": 1}},
        0.7,
    ),
    "trust_bot": _text_spec(
        [_num("runs", 500, 5), _num("ask_pct", 100, 10), _num("overruled_pct", 100, 10)],
        {"autonomous": {"ask_all": 8, "ask_outward": 4}, "ask_outward": {"ask_all": 2}},
        0.8,
    ),
    "keep_bot": _text_spec(
        [_num("runs", 500, 5), _num("done_pct", 100, 10), _num("overruled_pct", 100, 10)],
        {"retire": {"keep": 4, "fix": 2}, "keep": {"retire": 1, "fix": 1}},
        0.7,
    ),
}


def read_env(path: Path) -> Dict[str, str]:
    """KEY=value lines (a .env file); {} when there is none."""
    try:
        text = path.read_text("utf-8")
    except OSError:
        return {}
    found = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            if k.startswith("export "):
                k = k[len("export "):].strip()
            found[k] = v.strip().strip("'\"")
    return found


def api_key(root: Optional[Path] = None) -> Optional[str]:
    """The Ada API key bots run on: GLYPHH_API_KEY, else GLYPHH_API_KEY in the bots' .env (keep it mode 600); None
    leaves it to `Ada()` (the key `glyphh login` kept)."""
    return os.environ.get("GLYPHH_API_KEY") or read_env((root or bots_root()) / ".env").get("GLYPHH_API_KEY") or None


def connect(root: Optional[Path] = None) -> Ada:
    return Ada(key=api_key(root))


def _files(folder: Path, title: str) -> str:
    """An example bot's files, for the builder's brief."""
    files = sorted(p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    shown = "\n\n".join(f"=== {p.relative_to(folder)} ===\n{p.read_text('utf-8')}" for p in files)
    return f"## {title}\n\n{shown}"


def slug_of(job: str) -> str:
    """A bot's slug from its job: its first three words that say something, snake_case."""
    words = [w for w in re.findall(r"[a-z0-9]+", job.lower()) if w not in STOPWORDS][:3]
    slug = "_".join(words)[:40].strip("_") or "bot"
    return slug if slug[0].isalpha() else f"bot_{slug}"[:40]


class Orchestrator:
    """The bots in `root` (GLYPHH_BOTS, else ~/.glyphh/bots) and the orchestrator that makes, trusts and keeps them.
    `ask`, `echo`, `notify`, `fetch` and `today` are handed to every bot's Runner."""

    def __init__(
        self,
        ada: Ada,
        *,
        root: Optional[Path] = None,
        claude: Optional[Claude] = None,
        ask: Optional[Ask] = None,
        echo: Optional[Callable[[str], None]] = None,
        notify: Optional[Callable[[str, str], None]] = None,
        fetch: Optional[Fetch] = None,
        today: Optional[Callable[[], dt.date]] = None,
        now: Optional[Callable[[], dt.datetime]] = None,
    ) -> None:
        self.ada = ada
        self.root = Path(root) if root else bots_root()
        self.claude = claude or Claude()
        self.ask, self.echo = ask, echo or (lambda line: None)
        self._runner_kw: Dict[str, Any] = {"notify": notify, "fetch": fetch, "today": today, "now": now}
        self.root.mkdir(parents=True, exist_ok=True)
        with self._db() as c, c:
            c.execute("CREATE TABLE IF NOT EXISTS bots (slug TEXT PRIMARY KEY, job TEXT, made REAL, trust TEXT, keep TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS wrong (slug TEXT, run TEXT, at REAL)")

    def _db(self) -> "closing[sqlite3.Connection]":
        return closing(sqlite3.connect(self.root / "orchestrator.sqlite", timeout=30))

    @staticmethod
    def model(name: str) -> str:
        """The orchestrator's Ada model of this name: orch-<name>."""
        return model_name("orch", name)

    # its own models

    def ensure(self) -> Dict[str, Any]:
        """Make the orchestrator's memory and gate models that are not there yet (its first rule kept once)."""
        have = {m.name for m in self.ada.models()}
        made = []
        for kind in KINDS:
            if self.model(kind) not in have:
                self.ada.create_model(self.model(kind), {**MEMORY_SPEC, "name": self.model(kind)})
                made.append(self.model(kind))
        for name, spec in GATES.items():
            if self.model(name) not in have:
                self.ada.create_model(self.model(name), {**spec, "name": self.model(name)})
                made.append(self.model(name))
        if self.model("instructions") in made:
            remember(self.ada, self.model("instructions"), "instructions", FIRST_RULE, when="seed")
        return {"orchestrator": "ready", "made": made, "bots": str(self.root)}

    def remember(self, text: str, when: str = "", kind: str = "memory") -> None:
        """Keep a line in the orchestrator's own memory (a bot that makes bots keeps its findings here)."""
        remember(self.ada, self.model(kind), kind, text, when=when)

    # the bots

    def bot(self, slug: str) -> Bot:
        folder = self.root / slug
        if not (folder / "bot.json").exists():
            raise BotError(f"no bot {slug} in {self.root}: `glyphh bot install <folder>` or `glyphh bot new \"<job>\"`")
        return Bot.load(folder)

    def runner(self, bot: Union[str, Bot]) -> Runner:
        b = self.bot(bot) if isinstance(bot, str) else bot
        return Runner(b, self.ada, claude=self.claude, orchestrator=self, ask=self.ask, echo=self.echo,
                      **self._runner_kw)

    def adopt(self, slug: str, job: str, trust: str = "ask_all", keep: str = "keep") -> None:
        """The orchestrator takes a bot on: it asks for every approval (ask_all) until it earns more trust."""
        if trust not in TRUST or keep not in KEEP:
            raise BotError(f"trust is one of {', '.join(TRUST)}; keep one of {', '.join(KEEP)}")
        with self._db() as c, c:
            c.execute(
                "INSERT INTO bots VALUES (?, ?, ?, ?, ?) ON CONFLICT(slug) DO UPDATE SET job=excluded.job",
                (slug, job, time.time(), trust, keep),
            )

    def _column(self, slug: str, column: str, default: str) -> str:
        with self._db() as c:
            row = c.execute(f"SELECT {column} FROM bots WHERE slug = ?", (slug,)).fetchone()  # noqa: S608  a fixed column
        return str(row[0]) if row and row[0] else default

    def trust_of(self, slug: str) -> str:
        return self._column(slug, "trust", "ask_all")

    def keep_of(self, slug: str) -> str:
        return self._column(slug, "keep", "keep")

    def adopted(self) -> List[Dict[str, Any]]:
        with self._db() as c:
            rows = c.execute("SELECT slug, job, made, trust, keep FROM bots ORDER BY made").fetchall()
        return [{"bot": r[0], "job": r[1], "made": r[2], "trust": r[3], "keep": r[4]} for r in rows]

    def install(self, source: Union[str, Path], job: Optional[str] = None, trust: str = "ask_all") -> Dict[str, Any]:
        """Install a bot: a package folder (copied into the bots' home unless it is there) or the slug of one already
        there. Its models are made, its seed kept, and the orchestrator takes it on."""
        path = Path(source).expanduser()
        if not (path / "bot.json").exists():
            path = self.root / str(source)
        bot = Bot.load(path)
        target = self.root / bot.slug
        if path.resolve() != target.resolve():
            shutil.copytree(path, target, ignore=COPY_SKIP, dirs_exist_ok=True)
            bot = Bot.load(target)
        self.ensure()
        out = self.runner(bot).install()
        self.adopt(bot.slug, job or str(bot.spec.get("summary") or bot.name), trust)
        return {**out, "folder": str(target), "trust": self.trust_of(bot.slug)}

    def overruled(self, slug: str, run_id: str) -> None:
        with self._db() as c, c:
            c.execute("INSERT INTO wrong VALUES (?, ?, ?)", (slug, run_id, time.time()))

    def after_run(self, bot: Bot, run_id: str, status: str, data: Mapping[str, Any]) -> None:
        """Every bot run, kept in the orchestrator's memory: what the bot is, how its gates went, how it ended."""
        gates = ", ".join(f"{n} {g['outcome']} by {g['by']}" for n, g in (data.get("_gates") or {}).items())
        self.remember(
            f"bot {bot.slug} ({bot.spec.get('summary', '')}; touches {bot.touches}): run {run_id} {status}; "
            f"{gates or 'no gate'}",
            when="bot run",
        )

    # its gates

    def gate(self, name: str, case: Dict[str, Any], answer: Optional[str], question: str) -> Dict[str, Any]:
        """Ada's call when it is sure and no answer is given; else the person's answer, kept as a precedent. With no
        answer and nobody to ask, `outcome` is None and the question is said."""
        options = OUTCOMES[name]
        if answer is not None and answer not in options:
            raise BotError(f"{answer} is not an answer to {name}: one of {', '.join(options)}")
        model = self.ada.model(self.model(name))
        n = held(self.ada, self.model(name))
        d = model.decide(case) if n else None
        if answer is None and d and not d.ask and d.outcome in options:
            self.echo(f"orchestrator gate {name}: {d.outcome} (from {n} precedents), decided by Ada")
            return {"gate": name, "outcome": d.outcome, "by": "ada"}
        guess = d.outcome if d else None
        if answer is None and self.ask:
            why = f"Ada would say {guess}, not sure enough" if d else "no precedents yet"
            while answer not in options:
                answer = self.ask(f"{question} ({why})", options).strip().lower()
        if answer is None:
            return {"gate": name, "outcome": None, "question": question, "options": options, "guess": guess}
        model.record(case, answer)
        self.echo(f"orchestrator gate {name}: {answer}, the person's call, kept as precedent {n + 1}")
        return {"gate": name, "outcome": answer, "by": "person"}

    # making a bot

    def new(self, job: str, recurs: int = 7, touches: str = "read_only", answer: Optional[str] = None) -> Dict[str, Any]:
        """Should this job become a bot (make_bot)? If so, the builder writes it, it is checked, installed and taken
        on with trust ask_all. `recurs`: how many times a week the job comes up; `touches`: the most outward thing
        it may do."""
        if touches not in TOUCHES:
            raise BotError(f"touches is one of {', '.join(TOUCHES)}")
        self.ensure()
        learned = recall(self.ada, self.model("memory"), job, 12)
        similar = len([x for x in learned if x.startswith("made bot")])
        slug = self._free_slug(slug_of(job))
        case = {"o": {"s": {"text": job, "touches": touches, "recurs_per_week": max(0, min(recurs, 50)),
                            "similar_bots": min(similar, 20), "key": f"{slug}-{int(time.time())}"}}}
        call = self.gate("make_bot", case, answer, f"Make a bot for: {job}?")
        if call["outcome"] is None:
            return {"status": "needs_input", **call, "job": job,
                    "answer_with": f"glyphh bot new {json.dumps(job)} --recurs {recurs} --touches {touches} --answer <one>"}
        if call["outcome"] != "make":
            return {"status": "not_made", **call, "job": job}
        folder = self.root / slug
        folder.mkdir(parents=True)
        said = self.claude.build(self._brief(job, slug, touches, learned), folder)
        self.echo(f"builder: {said[:400]}")
        bot = self._accept(folder, slug, touches)
        installed = self.runner(bot).install()
        self.adopt(slug, job, "ask_all")
        self.remember(
            f"made bot {slug} for: {job}; touches {bot.touches}; gates {', '.join(bot.gates) or 'none'}; loop "
            f"{' > '.join(s['id'] for s in bot.loop)}",
            when="made bot",
        )
        return {"status": "made", "bot": slug, "folder": str(folder), "builder": said, "made": installed["made"],
                "trust": "ask_all", "run_with": f"glyphh bot run {slug}"}

    def _free_slug(self, slug: str) -> str:
        found, n = slug, 2
        while (self.root / found).exists():
            found, n = f"{slug[:37]}_{n}", n + 1
        return found

    def _brief(self, job: str, slug: str, touches: str, learned: List[str]) -> str:
        example = "\n\n".join(_files(folder, title) for folder, title in (
            (EXAMPLE, "A bot with one gate on the whole run (is today worth a summary?)"),
            (EXAMPLE_ITEMS, "A bot with a per-item gate (each story of a list: read or skip), the gate for lists"),
        ))
        before = (
            "What you have learned from the bots you made before (use what worked, avoid what didn't):\n"
            + "\n".join(f"- {x}" for x in learned)
            if learned
            else "This is the first bot you make."
        )
        return (
            f"Build a bot for this job: {job}\n\nWrite its package into the current folder (slug `{slug}`): bot.json, "
            f"agent.md, program.py and skills/*/SKILL.md, following the format below exactly. The most outward thing "
            f"it may do is `{touches}`: its bot.json says `\"touches\": \"{touches}\"` or less, and any step that "
            f"sends, posts, pays or deletes has an `approval`.\n\n{BUILDING.read_text('utf-8')}\n\n"
            f"Two example bots that work:\n\n{example}\n\n{before}\n\n"
            "When the files are written, answer with one line: the bot's gates and why each is there."
        )

    def _accept(self, folder: Path, slug: str, touches: str) -> Bot:
        """The builder's bot, checked like any other, and held to what was asked; one that is not right is moved
        aside to .rejected/ and said."""
        problems: List[str] = []
        bot: Optional[Bot] = None
        try:
            bot = Bot.load(folder)
        except BotError as e:
            problems = e.problems or [e.message]
        if bot is not None:
            if bot.slug != slug:
                problems.append(f"its slug is {bot.slug}, not {slug}")
            if TOUCHES.index(bot.touches) > TOUCHES.index(touches):
                problems.append(f"it touches {bot.touches}, more than the {touches} asked")
        if not problems:
            assert bot is not None
            return bot
        aside = self.root / ".rejected" / f"{slug}-{int(time.time())}-{uuid.uuid4().hex[:4]}"
        aside.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(aside))
        raise BotError(f"the builder's bot is not right (kept in {aside}): {problems[0]}", problems)

    # trust and keep

    def record_of(self, slug: str) -> Dict[str, int]:
        """A bot's record: its runs, how often its gates asked the person, how often it was overruled, how often a
        run finished."""
        rows = RunStore(self.root / slug).recent()
        gates = [g for r in rows for g in (r["data"].get("_gates") or {}).values()]
        calls = sum(g.get("asked", 0) + g.get("decided", 0) + g.get("defaulted", 0) if g.get("each") else 1 for g in gates)
        asked = sum(g.get("asked", 0) if g.get("each") else int(g.get("by") == "person") for g in gates)
        with self._db() as c:
            wrong = c.execute("SELECT COUNT(*) FROM wrong WHERE slug = ?", (slug,)).fetchone()[0]
        done = sum(1 for r in rows if r["status"] == "done")

        def pct(a: int, b: int) -> int:
            return min(100, round(100 * a / b)) if b else 0

        return {"runs": len(rows), "ask_pct": pct(asked, calls), "overruled_pct": pct(wrong, len(rows)),
                "done_pct": pct(done, len(rows))}

    def case_for(self, slug: str, name: str) -> Dict[str, Any]:
        bot, r = self.bot(slug), self.record_of(slug)
        s: Dict[str, Any] = {"text": str(bot.spec.get("summary") or slug), "touches": bot.touches,
                             "runs": min(r["runs"], 500), "overruled_pct": r["overruled_pct"],
                             "key": f"{slug}-{name}-{r['runs']}"}
        s.update({"ask_pct": r["ask_pct"]} if name == "trust_bot" else {"done_pct": r["done_pct"]})
        return {"o": {"s": s}}

    def _apply(self, slug: str, name: str, outcome: str) -> None:
        column = "trust" if name == "trust_bot" else "keep"
        with self._db() as c, c:
            c.execute(f"UPDATE bots SET {column} = ? WHERE slug = ?", (outcome, slug))  # noqa: S608  a fixed column

    def review(self, answers: Optional[Mapping[str, str]] = None) -> List[Dict[str, Any]]:
        """trust_bot and keep_bot for every bot, from its record: Ada's call where it is sure, else the person's
        (`answers`: {"<bot>.trust_bot": "ask_outward", ...}), each applied; the rest said as questions."""
        answers = answers or {}
        out = []
        for b in self.adopted():
            slug = b["bot"]
            if not (self.root / slug / "bot.json").exists():
                continue
            for name in ("trust_bot", "keep_bot"):
                record = self.record_of(slug)
                call = self.gate(name, self.case_for(slug, name), answers.get(f"{slug}.{name}"),
                                 f"{slug} {json.dumps(record)}: {name}?")
                if call["outcome"]:
                    self._apply(slug, name, call["outcome"])
                out.append({"bot": slug, **call, "record": record})
        return out

    def verdict(self, slug: str, which: str, outcome: str) -> Dict[str, Any]:
        """The person's trust or keep call on a bot: kept as a precedent of the gate, and applied."""
        if which not in ("trust", "keep"):
            raise BotError("a verdict is on trust or keep")
        name = f"{which}_bot"
        self.bot(slug)
        call = self.gate(name, self.case_for(slug, name), outcome, "")
        self._apply(slug, name, outcome)
        return {"bot": slug, which: outcome, "by": call["by"]}

    def status(self) -> Dict[str, Any]:
        have = {m.name: m.precedents for m in self.ada.models()}
        bots = []
        for b in self.adopted():
            there = (self.root / b["bot"] / "bot.json").exists()
            paused = RunStore(self.root / b["bot"]).state("_paused") if there else None
            bots.append({**{k: v for k, v in b.items() if k != "made"},
                         **({"record": self.record_of(b["bot"])} if there else {"missing": True}),
                         **({"paused": paused} if paused else {})})
        return {
            "bots_home": str(self.root),
            "gates": {n: have.get(self.model(n), 0) for n in GATES},
            "memory": {k: have.get(self.model(k), 0) for k in KINDS},
            "bots": bots,
        }
