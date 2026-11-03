"""The orchestrator: the Claude that makes bots, and learns how to make them.

It has its own memory and three Ada gates of its own, each learning only from the person's verdicts and the bots'
real outcomes, never from its own guesses:

  make_bot   should this job become a bot (make / not_yet / no)
  trust_bot  how far a bot may act without asking (autonomous / ask_outward / ask_all)
  keep_bot   keep, fix or retire a bot, from its record

Every bot it makes gets gates of its own (botrun's). Every bot run is kept in the orchestrator's memory, so when it
builds the next bot, its builder agent starts from what worked for the bots before: which gates, which steps, how
they did. The bots learn their jobs; the orchestrator learns to build bots.

  botrun orch install
  botrun orch new "<job>" --recurs N --touches read_only|drafts|sends|pays|deletes [--answer make|not_yet|no]
  botrun orch review [--answer <bot>.trust_bot=<outcome> <bot>.keep_bot=<outcome> ...]   trust and keep, from records
  botrun orch verdict <bot> trust|keep <outcome>        the person's call, kept as a precedent and applied
  botrun orch status"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import botrun

HERE = Path(__file__).resolve().parent
DB = HERE / "orchestrator.sqlite"
TOUCHES = ["read_only", "drafts", "sends", "pays", "deletes"]


def _text_spec(name: str, extra: list[dict], costs: dict, ask_below: float) -> dict:
    return {"name": name, "layers": [{"name": "o", "segments": [{"name": "s", "roles": [
        {"name": "text", "text_encoding": "bag_of_words"}, {"name": "touches"}, *extra,
        {"name": "key", "key_part": True, "similarity_weight": 0}]}]}],
        "output": {"costs": costs, "ask_below": ask_below}}


def _num(name: str, hi: int, step: int) -> dict:
    return {"name": name, "numeric_config": {"min_value": 0, "max_value": hi, "bin_width": step}}


GATES = {
    "make_bot": _text_spec("make_bot", [_num("recurs_per_week", 50, 1), _num("similar_bots", 20, 1)],
                           {"make": {"no": 5, "not_yet": 1}, "not_yet": {"make": 1}, "no": {"make": 1}}, 0.7),
    "trust_bot": _text_spec("trust_bot", [_num("runs", 500, 5), _num("ask_pct", 100, 10), _num("overruled_pct", 100, 10)],
                            {"autonomous": {"ask_all": 8, "ask_outward": 4}, "ask_outward": {"ask_all": 2}}, 0.8),
    "keep_bot": _text_spec("keep_bot", [_num("runs", 500, 5), _num("done_pct", 100, 10), _num("overruled_pct", 100, 10)],
                           {"retire": {"keep": 4, "fix": 2}, "keep": {"retire": 1, "fix": 1}}, 0.7),
}
OUTCOMES = {"make_bot": ["make", "not_yet", "no"], "trust_bot": ["autonomous", "ask_outward", "ask_all"],
            "keep_bot": ["keep", "fix", "retire"]}


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS bots (slug TEXT PRIMARY KEY, job TEXT, made REAL, trust TEXT, keep TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS wrong (slug TEXT, run TEXT, at REAL)")
    return c


def model(name: str) -> str:
    return "orch-" + name.replace("_", "-")


def trust_of(slug: str) -> str:
    row = db().execute("SELECT trust FROM bots WHERE slug = ?", (slug,)).fetchone()
    return (row and row[0]) or "ask_all"


# --- the orchestrator's own learning ---------------------------------------------------------------------------------


def install() -> None:
    client = botrun.ada()
    have = {m.name for m in client.models()}
    for kind in botrun.KINDS:
        if model(kind) not in have:
            client.create_model(model(kind), {**botrun.MEMORY_SPEC, "name": model(kind)})
            print(f"made {model(kind)}")
    for name, spec in GATES.items():
        if model(name) not in have:
            client.create_model(model(name), {**spec, "name": model(name)})
            print(f"made {model(name)}")
    botrun.remember(client, model("instructions"), "instructions",
                    "Never let a bot act outward (send, post, pay, delete) without the person's yes until trust_bot "
                    "and the person agree it may.", when="seed")
    print("orchestrator installed")


def gate(client, name: str, case: dict, answer: str | None, question: str) -> str | None:
    """The orchestrator's gate: Ada's call when it is sure; else the person's answer (kept as a precedent), or None
    when there is no answer yet (the question is printed for them)."""
    m = client.model(model(name))
    held = next((x.precedents for x in client.models() if x.name == model(name)), 0)
    d = m.decide(case) if held else None
    if d and not d.ask and answer is None:
        print(f"orchestrator gate {name}: {d.outcome} (from {held} precedents) — decided by Ada")
        return d.outcome
    if answer is None:
        guess = f"Ada would say {d.outcome}, not sure enough" if d else "no precedents yet"
        print(f"? {question} ({guess}) — answer with one of {OUTCOMES[name]}")
        return None
    m.record(case, answer)
    print(f"orchestrator gate {name}: {answer} — the person's call, kept as precedent {held + 1}")
    return answer


def after_run(bot: botrun.Bot, run_id: str, status: str, data: dict) -> None:
    """Every bot run, kept in the orchestrator's memory: what the bot is, how its gates went, how it ended."""
    gates = ", ".join(f"{n} {g['outcome']} by {g['by']}" for n, g in data.get("_gates", {}).items()) or "no gate"
    botrun.remember(botrun.ada(), model("memory"), "memory",
                    f"bot {bot.slug} ({bot.spec.get('summary', '')}; touches {bot.spec.get('touches', 'read_only')}): "
                    f"run {run_id} {status}; {gates}", when="bot run")


# --- making a bot ------------------------------------------------------------------------------------------------------


def slug_of(job: str) -> str:
    words = re.findall(r"[a-z]+", job.lower())
    return "_".join([w for w in words if w not in {"a", "the", "and", "of", "to", "for", "my", "me", "every", "each"}][:3])


def build(job: str, slug: str, learned: list[str]) -> Path:
    """The builder agent writes the bot's package into bots/<slug>/, from the job, the format, an example bot, and
    what the orchestrator has learned from the bots before."""
    out = botrun.BOTS / slug
    out.mkdir(parents=True, exist_ok=True)
    example = botrun.BOTS / "launch_watch"
    files = "\n\n".join(f"=== {p.relative_to(example)} ===\n{p.read_text()}" for p in
                        [example / "bot.json", example / "agent.md", example / "program.py",
                         example / "skills" / "launch-summary" / "SKILL.md"])
    prompt = (f"Build a bot for this job: {job}\n\nWrite its package into the current folder (slug `{slug}`): bot.json, "
              f"agent.md, program.py and skills/*/SKILL.md, following the format below exactly.\n\n"
              f"{(HERE / 'BUILDING.md').read_text()}\n\nAn example bot that works:\n\n{files}\n\n"
              + ("What you have learned from the bots you made before (use what worked, avoid what didn't):\n"
                 + "\n".join(f"- {x}" for x in learned) if learned else "This is the first bot you make.")
              + "\n\nWhen the files are written, answer with one line: the bot's gates and why each is there.")
    cmd = ["claude", "-p", "--tools", "Read,Write", "--permission-mode", "acceptEdits", "--strict-mcp-config",
           "--setting-sources", "", "--output-format", "json", "--no-session-persistence", "--max-turns", "20", prompt]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=out, timeout=900)
    if res.returncode:
        sys.exit(f"the builder failed: {res.stderr[:400] or res.stdout[:400]}")
    print(f"builder: {json.loads(res.stdout).get('result', '').strip()[:400]}")
    return out


def check(slug: str) -> botrun.Bot:
    bot = botrun.Bot(slug)
    for step in bot.spec["loop"]:
        if "run" in step and not hasattr(bot.program, step["run"]):
            sys.exit(f"{slug}: program.py has no {step['run']}")
        if "gate" in step and not hasattr(bot.program, bot.spec["gates"][step["gate"]]["case"]):
            sys.exit(f"{slug}: program.py has no case function for gate {step['gate']}")
    return bot


def new(job: str, recurs: int, touches: str, answer: str | None) -> None:
    client = botrun.ada()
    learned = botrun.recall(client, model("memory"), job, 12)
    similar = len([x for x in learned if x.startswith("made bot")])
    case = {"o": {"s": {"text": job, "touches": touches, "recurs_per_week": min(recurs, 50),
                        "similar_bots": min(similar, 20), "key": f"{slug_of(job)}-{int(time.time())}"}}}
    call = gate(client, "make_bot", case, answer, f"Make a bot for: {job}?")
    if call != "make":
        print("no bot made" if call else "waiting for your answer")
        return
    slug = slug_of(job)
    build(job, slug, learned)
    bot = check(slug)
    botrun.install(bot)
    db().execute("INSERT OR REPLACE INTO bots VALUES (?, ?, ?, 'ask_all', 'keep')", (slug, job, time.time())).connection.commit()
    botrun.remember(client, model("memory"), "memory",
                    f"made bot {slug} for: {job}; touches {bot.spec.get('touches')}; gates "
                    f"{', '.join(bot.spec.get('gates', {}))}; loop {' > '.join(s['id'] for s in bot.spec['loop'])}",
                    when="made bot")
    print(f"made bot {slug}: trust ask_all until it earns more; run it with `botrun run {slug}`")


# --- trust and keep ----------------------------------------------------------------------------------------------------


def record_of(slug: str) -> dict:
    rows = botrun.Bot(slug).db.execute("SELECT status, data FROM runs").fetchall()
    runs = len(rows)
    gates = [g for _, d in rows for g in json.loads(d).get("_gates", {}).values()]
    asked = sum(1 for g in gates if g["by"] == "person")
    wrong = db().execute("SELECT COUNT(*) FROM wrong WHERE slug = ?", (slug,)).fetchone()[0]
    done = sum(1 for s, _ in rows if s == "done")
    pct = lambda a, b: round(100 * a / b) if b else 0  # noqa: E731
    return {"runs": runs, "ask_pct": pct(asked, len(gates)), "overruled_pct": pct(wrong, runs), "done_pct": pct(done, runs)}


def case_for(slug: str, name: str) -> dict:
    bot, r = botrun.Bot(slug), record_of(slug)
    s = {"text": bot.spec.get("summary", slug), "touches": bot.spec.get("touches", "read_only"),
         "runs": min(r["runs"], 500), "overruled_pct": r["overruled_pct"], "key": f"{slug}-{name}-{r['runs']}"}
    s.update({"ask_pct": r["ask_pct"]} if name == "trust_bot" else {"done_pct": r["done_pct"]})
    return {"o": {"s": s}}


def apply(slug: str, name: str, outcome: str) -> None:
    col = "trust" if name == "trust_bot" else "keep"
    db().execute(f"UPDATE bots SET {col} = ? WHERE slug = ?", (outcome, slug)).connection.commit()
    print(f"{slug}: {col} {outcome}")


def review(answers: dict[str, str]) -> None:
    client = botrun.ada()
    for (slug,) in db().execute("SELECT slug FROM bots").fetchall():
        for name in ("trust_bot", "keep_bot"):
            got = gate(client, name, case_for(slug, name), answers.get(f"{slug}.{name}"),
                       f"{slug} {record_of(slug)}: {name}?")
            if got:
                apply(slug, name, got)


def verdict(slug: str, which: str, outcome: str) -> None:
    name = "trust_bot" if which == "trust" else "keep_bot"
    gate(botrun.ada(), name, case_for(slug, name), outcome, "")
    apply(slug, name, outcome)


def status() -> None:
    client = botrun.ada()
    held = {m.name: m.precedents for m in client.models()}
    for name in GATES:
        print(f"orchestrator gate {name}: {held.get(model(name), 0)} precedents")
    print(f"orchestrator memory: {held.get(model('memory'), 0)}")
    for slug, job, _, trust, keep in db().execute("SELECT * FROM bots").fetchall():
        print(f"bot {slug}: trust {trust}, {keep}; {record_of(slug)}; job: {job}")


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else ""
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
    if cmd == "install":
        install()
    elif cmd == "new":
        new(argv[1], int(opt("--recurs", "7")), opt("--touches", "read_only"), opt("--answer"))
    elif cmd == "review":
        # --answer <bot>.trust_bot=<outcome> <bot>.keep_bot=<outcome> ...
        review(dict(a.split("=", 1) for a in argv[argv.index("--answer") + 1:]) if "--answer" in argv else {})
    elif cmd == "verdict":
        verdict(argv[1], argv[2], argv[3])
    elif cmd == "status":
        status()
    else:
        sys.exit(__doc__)
