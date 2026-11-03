#!/usr/bin/env python3
"""botrun: the orchestrator. A bot's program controls its Claude agent: botrun walks the bot's loop, runs its code
steps itself, asks Ada at its gates, and calls the bot's Claude agent (`claude -p`) only for the steps that need
judgment, with the step's skill and the bot's memory (its own, and the person's glyphh) put before it.

Gates learn: each is an Ada model of the bot's own. Under its confidence, or with no precedent like the case, the
person is asked; their answer is recorded as a precedent, so the gate asks less run after run. A wrong call is
corrected with `botrun wrong`, recorded the same way.

  botrun install <bot>              make the bot's gate and memory models, remember its seed
  botrun run <bot> [--routine]      one run of the loop (--routine: nobody watching, a question stops the run)
  botrun continue <bot> [answer]    carry on the run that stopped, with the answer to its question
  botrun wrong <bot> <run> <outcome>  the gate decided that run wrong: record what it should have been
  botrun status <bot>               the last runs and each gate's precedents
  botrun routine <bot>              install the bot's routine as a launchd job (runs `run --routine` on its cron)

The Ada API key is GLYPHH_API_KEY, or ~/.glyphh/bots/.env (mode 600). Ada Cloud: https://ada.glyphh.ai."""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from glyphh import Ada

HERE = Path(__file__).resolve().parent
BOTS = HERE / "bots"
ENV = Path.home() / ".glyphh" / "bots" / ".env"
UA = "glyphh-bot/0.1"
MEMORY_SPEC = {
    "name": "bot-memory",
    "seed": 7,
    "dimension": 2048,
    "layers": [{"name": "m", "segments": [{"name": "s", "roles": [
        {"name": "cue", "text_encoding": "bag_of_words"},
        {"name": "kind", "similarity_weight": 0.1},
        {"name": "key", "key_part": True, "similarity_weight": 0},
    ]}]}],
}
KINDS = ("memory", "instructions", "personality")


class Stop(Exception):
    """The run stops here: `status` needs_input or failed, with why."""

    def __init__(self, status: str, reason: str, pending: dict | None = None):
        super().__init__(reason)
        self.status, self.reason, self.pending = status, reason, pending or {}


# --- the bot --------------------------------------------------------------------------------------------------------


class Bot:
    def __init__(self, slug: str):
        self.dir = BOTS / slug
        self.spec = json.loads((self.dir / "bot.json").read_text())
        self.slug = self.spec["slug"]
        self.db = sqlite3.connect(self.dir / "runs.sqlite")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, started REAL, status TEXT, at INT, data TEXT,"
            " pending TEXT, reason TEXT, log TEXT)"
        )
        self.db.execute("CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT)")
        self.db.commit()
        spec = importlib.util.spec_from_file_location(f"bot_{self.slug}", self.dir / "program.py")
        self.program = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.program)

    def gate_model(self, gate: str) -> str:
        return f"bot-{self.slug.replace('_', '-')}-gate-{gate.replace('_', '-')}"

    def memory_model(self, kind: str) -> str:
        return f"bot-{self.slug.replace('_', '-')}-{kind}"

    def agent(self) -> tuple[str, dict]:
        text = (self.dir / self.spec.get("agent", "agent.md")).read_text()
        m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
        meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
        meta = {k.strip(): v.strip() for k, v in meta.items()}
        return meta["name"], {"description": meta.get("description", ""), "prompt": m.group(2).strip(),
                              "model": meta.get("model", "sonnet")}


class Ctx:
    """What a code step gets: the bot's folder, its own SQLite, HTTP to its hosts only, today, its state."""

    def __init__(self, bot: Bot, run_id: str):
        self.bot, self.run_id, self.dir = bot, run_id, bot.dir
        self.today = dt.date.today()
        self.lines: list[str] = []

    def http_json(self, url: str) -> Any:
        host = urllib.parse.urlparse(url).hostname
        if host not in self.bot.spec.get("hosts", []):
            raise Stop("failed", f"{host} is not one of the bot's hosts")
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as res:
            return json.load(res)

    def db(self) -> sqlite3.Connection:
        return sqlite3.connect(self.dir / "data.sqlite")

    def state(self, k: str) -> str | None:
        row = self.bot.db.execute("SELECT v FROM state WHERE k = ?", (k,)).fetchone()
        return row[0] if row else None

    def set_state(self, k: str, v: str) -> None:
        self.bot.db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (k, v))
        self.bot.db.commit()

    def gate(self, name: str):
        """One of the bot's gate models, for code that asks Ada itself (and records what the world answered)."""
        return ada().model(self.bot.gate_model(name))

    def log(self, line: str) -> None:
        self.lines.append(line)
        print(f"  {line}")


# --- Ada: gates and memory ------------------------------------------------------------------------------------------


def ada() -> Ada:
    key = os.environ.get("GLYPHH_API_KEY")
    if not key and ENV.exists():
        found = dict(l.split("=", 1) for l in ENV.read_text().splitlines() if "=" in l)
        key = found.get("GLYPHH_API_KEY", "").strip()
    if not key:
        sys.exit("botrun: no Ada API key (GLYPHH_API_KEY, or ~/.glyphh/bots/.env)")
    return Ada(key=key)


def _memory_case(cue: str, kind: str | None = None, text: str | None = None) -> dict:
    s: dict[str, Any] = {"cue": cue}
    if kind:
        s["kind"] = kind
    if text:
        s["key"] = hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()[:16]
    return {"m": {"s": s}}


def remember(client: Ada, model: str, kind: str, text: str, when: str = "") -> None:
    client.model(model).record(_memory_case(f"{when} {text}".strip(), kind, text), text)


def recall(client: Ada, model: str, about: str, top: int) -> list[str]:
    try:
        trees = client.model(model).facts({"m": {"s": {"cue": about}}}, top=top).data
    except Exception:  # an empty model has nothing to say
        return []
    return [t["outcome"] for t in (trees or []) if t.get("score", 1) >= 0.05]


def glyphh_models(client: Ada) -> dict[str, str]:
    """The person's own glyphh (Agentic memory), by kind, if they have one."""
    found = {}
    for m in client.models():
        hit = re.fullmatch(r"me-[0-9a-f]{12}-agentic-memory-(\w+)", m.name)
        if hit and hit.group(1) in KINDS:
            found[hit.group(1)] = m.name
    return found


def memory_context(client: Ada, bot: Bot, about: str) -> str:
    """What is put before the agent: the person's rules and personality, then the bot's own, then what it recalls."""
    parts = []
    if bot.spec.get("reads_glyphh", True):
        mine = glyphh_models(client)
        for kind, title in (("instructions", "The person's rules"), ("personality", "How the person likes it")):
            got = recall(client, mine[kind], about, 10) if kind in mine else []
            if got:
                parts.append(f"{title}:\n" + "\n".join(f"- {g}" for g in got))
    for kind, title in (("instructions", "Your rules"), ("personality", "Your personality"),
                        ("memory", "What you remember from earlier runs")):
        got = recall(client, bot.memory_model(kind), about, 8)
        if got:
            parts.append(f"{title}:\n" + "\n".join(f"- {g}" for g in got))
    return "\n\n".join(parts)


# --- the loop -------------------------------------------------------------------------------------------------------


def fill(value: Any, data: dict) -> Any:
    """`$id` in a step's input or prompt: the earlier step's data (the whole value, or JSON inside a string)."""
    if isinstance(value, str) and re.fullmatch(r"\$\w+", value):
        return data.get(value[1:])
    if isinstance(value, str):
        return re.sub(r"\$(\w+)", lambda m: json.dumps(data.get(m.group(1)), default=str) if m.group(1) in data
                      else m.group(0), value)
    return value


def ask_person(question: str, options: list[str], routine: bool, pending: dict) -> str:
    if routine or not sys.stdin.isatty():
        raise Stop("needs_input", question, pending)
    while True:
        got = input(f"\n? {question} [{'/'.join(options)}] ").strip().lower()
        if got in options:
            return got


def gate_step(client: Ada, bot: Bot, ctx: Ctx, step: dict, data: dict, routine: bool, answer: str | None) -> str:
    name = step["gate"]
    gate = bot.spec["gates"][name]
    case = getattr(bot.program, gate["case"])(ctx, data)
    model = client.model(bot.gate_model(name))
    held = next((m.precedents for m in client.models() if m.name == model.name), 0)
    decision = model.decide(case) if held else None
    if decision and not decision.ask:
        best = max(decision.probabilities.values()) if decision.probabilities else 0
        ctx.log(f"gate {name}: {decision.outcome} (P {best:.2f}, from {held} precedents) — decided by Ada")
        data.setdefault("_gates", {})[name] = {"case": case, "outcome": decision.outcome, "by": "ada"}
        return decision.outcome
    if answer is None:
        why = f"Ada's guess is {decision.outcome}, not sure enough" if decision else "no precedents yet"
        moved = json.dumps(case["day"]["moved"]) if "day" in case else json.dumps(case)
        answer = ask_person(f"Gate {name} ({why}). Today: {moved}. Which?", gate["outcomes"], routine,
                            {"gate": name, "case": case})
    model.record(case, answer)
    ctx.log(f"gate {name}: {answer} — the person's call, kept as precedent {held + 1}")
    data.setdefault("_gates", {})[name] = {"case": case, "outcome": answer, "by": "person"}
    return answer


def agent_step(client: Ada, bot: Bot, ctx: Ctx, step: dict, data: dict) -> str:
    name, agent = bot.agent()
    prompt = fill(step["agent"], data)
    if step.get("skill"):
        skill = (bot.dir / "skills" / step["skill"] / "SKILL.md").read_text()
        prompt += f"\n\nHow to do it (your skill {step['skill']}):\n{skill}"
    known = memory_context(client, bot, prompt[:1500])
    if known:
        prompt = f"{known}\n\n---\n\n{prompt}"
    # only what the program gives it: no tools, no MCP servers, no settings, hooks or CLAUDE.md (measured: $0.006 a
    # step, against $0.44 with a full session's context)
    cmd = ["claude", "-p", "--agents", json.dumps({name: agent}), "--agent", name, "--tools", "",
           "--strict-mcp-config", "--setting-sources", "", "--output-format", "json", "--no-session-persistence",
           "--max-turns", str(bot.spec.get("limits", {}).get("agent_turns", 3)), prompt]
    ctx.log(f"agent {name}: {step['id']} ({len(prompt)} chars in, memory {'yes' if known else 'none yet'})")
    out = subprocess.run(cmd, capture_output=True, text=True, cwd="/tmp",
                         timeout=bot.spec.get("limits", {}).get("seconds", 300))
    if out.returncode:
        raise Stop("failed", f"the agent failed: {out.stderr.strip()[:300] or out.stdout.strip()[:300]}")
    answer = json.loads(out.stdout).get("result", "").strip()
    if step.get("remember"):
        remember(client, bot.memory_model("memory"), "memory", f"{ctx.today}: {step['id']}: {answer[:1500]}",
                 when=f"run {ctx.run_id}")
    return answer


def walk(bot: Bot, run_id: str, at: int, data: dict, routine: bool, answer: str | None = None) -> None:
    client = ada()
    ctx = Ctx(bot, run_id)
    loop = bot.spec["loop"]
    ids = [s["id"] for s in loop]
    status, reason, pending = "done", "", {}
    try:
        while at < len(loop):
            step = loop[at]
            if step.get("approval") and orch.trust_of(bot.slug) != "autonomous":
                said = answer or ask_person(f"{step['id']}: {step['approval']} — yes?", ["yes", "no"], routine,
                                            {"approval": step["id"]})
                answer = None
                ctx.log(f"approval {step['approval']}: {said} (the person's)")
                if said != "yes":
                    break
            if "run" in step:
                ctx.log(f"run {step['run']}")
                data[step["id"]] = getattr(bot.program, step["run"])(ctx, fill(step.get("input"), data))
                if isinstance(data[step["id"]], dict) and data[step["id"]].get("_end"):
                    ctx.log(f"the program ends the run here: {data[step['id']]['_end']}")  # a hard gate
                    break
            elif "gate" in step:
                outcome = gate_step(client, bot, ctx, step, data, routine, answer)
                answer = None
                data[step["id"]] = outcome
                target = step["on"][outcome]
                if target == "end":
                    ctx.log("the gate ends the run here")
                    break
                at = ids.index(target)
                save(bot, run_id, "running", at, data)
                continue
            elif "agent" in step:
                data[step["id"]] = agent_step(client, bot, ctx, step, data)
            at += 1
            save(bot, run_id, "running", at, data)
    except Stop as e:
        status, reason, pending = e.status, e.reason, e.pending
    save(bot, run_id, status, at, data, pending, reason, ctx.lines)
    outcome = f"{status}{': ' + reason if reason else ''}"
    print(f"\n{bot.slug} run {run_id}: {outcome}")
    if status in ("done", "failed"):
        orch.after_run(bot, run_id, status, data)
    if status != "running":
        remember(client, bot.memory_model("memory"), "memory",
                 f"{ctx.today}: run {run_id} ended {status}" + (f" at {loop[at]['id']}" if at < len(loop) else ""),
                 when="run outcome")
    if status != "done" and routine:
        notify(bot, f"{status} at {loop[at]['id']}: run `botrun continue {bot.slug}`")


def save(bot: Bot, run_id: str, status: str, at: int, data: dict, pending: dict | None = None, reason: str = "",
         lines: list[str] | None = None) -> None:
    bot.db.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
        " at=excluded.at, data=excluded.data, pending=excluded.pending, reason=excluded.reason, log=excluded.log",
        (run_id, time.time(), status, at, json.dumps(data, default=str), json.dumps(pending or {}), reason,
         "\n".join(lines or [])),
    )
    bot.db.commit()


def notify(bot: Bot, text: str) -> None:
    subprocess.run(["osascript", "-e", f'display notification "{text}" with title "{bot.spec["name"]}"'],
                   check=False, capture_output=True)


# --- commands -------------------------------------------------------------------------------------------------------


def install(bot: Bot) -> None:
    client = ada()
    have = {m.name for m in client.models()}
    for name, gate in bot.spec.get("gates", {}).items():
        model = bot.gate_model(name)
        if model not in have:
            client.create_model(model, {**gate["spec"], "name": model})
            print(f"made gate model {model}")
    for kind in KINDS:
        model = bot.memory_model(kind)
        if model not in have:
            client.create_model(model, {**MEMORY_SPEC, "name": model})
            print(f"made memory model {model}")
    for kind, texts in bot.spec.get("seed", {}).items():
        for text in texts:
            remember(client, bot.memory_model(kind), kind, text, when="seed")
    print(f"{bot.slug} installed")


def run(bot: Bot, routine: bool) -> None:
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    print(f"{bot.slug} run {run_id}{' (routine)' if routine else ''}")
    walk(bot, run_id, 0, {}, routine)


def carry_on(bot: Bot, answer: str | None) -> None:
    row = bot.db.execute("SELECT id, at, data FROM runs WHERE status = 'needs_input' ORDER BY started DESC LIMIT 1")
    found = row.fetchone()
    if not found:
        sys.exit(f"{bot.slug}: no run is waiting")
    run_id, at, data = found
    print(f"{bot.slug} run {run_id}: carrying on")
    walk(bot, run_id, at, json.loads(data), routine=False, answer=answer)


def wrong(bot: Bot, run_id: str, outcome: str) -> None:
    found = bot.db.execute("SELECT data FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not found:
        sys.exit(f"{bot.slug}: no run {run_id}")
    client = ada()
    orch.db().execute("INSERT INTO wrong VALUES (?, ?, ?)", (bot.slug, run_id, time.time())).connection.commit()
    for name, g in json.loads(found[0]).get("_gates", {}).items():
        client.model(bot.gate_model(name)).record(g["case"], outcome)
        print(f"gate {name}: run {run_id} recorded as {outcome} (it said {g['outcome']}, by {g['by']})")


def status(bot: Bot) -> None:
    client = ada()
    held = {m.name: m.precedents for m in client.models()}
    for name in bot.spec.get("gates", {}):
        print(f"gate {name}: {held.get(bot.gate_model(name), 0)} precedents")
    for kind in KINDS:
        print(f"memory {kind}: {held.get(bot.memory_model(kind), 0)}")
    rows = bot.db.execute("SELECT id, status, reason, data FROM runs ORDER BY started DESC LIMIT 10").fetchall()
    for run_id, st, reason, data in rows:
        gates = ", ".join(f"{n} {g['outcome']} by {g['by']}" for n, g in json.loads(data).get("_gates", {}).items())
        print(f"{run_id}  {st:<12} {gates}  {reason[:80]}")


def routine(bot: Bot) -> None:
    minute, hour = bot.spec["routine"]["cron"].split()[:2]
    label = f"ai.glyphh.bot.{bot.slug}"
    plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    logs = bot.dir / "routine.log"
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key><array>
    <string>{sys.executable}</string><string>{Path(__file__).resolve()}</string>
    <string>run</string><string>{bot.slug}</string><string>--routine</string>
  </array>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>{int(hour)}</integer><key>Minute</key><integer>{int(minute)}</integer></dict>
  <key>StandardOutPath</key><string>{logs}</string><key>StandardErrorPath</key><string>{logs}</string>
</dict></plist>
""")
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist)], check=True)
    print(f"routine: {label} runs `botrun run {bot.slug} --routine` daily at {int(hour)}:{int(minute):02d} local")


def main(argv: list[str]) -> None:
    if argv[:1] == ["orch"]:
        return orch.main(argv[1:])
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd, bot = argv[0], Bot(argv[1])
    if cmd == "install":
        install(bot)
    elif cmd == "run":
        run(bot, "--routine" in argv)
    elif cmd == "continue":
        carry_on(bot, argv[2] if len(argv) > 2 else None)
    elif cmd == "wrong":
        wrong(bot, argv[2], argv[3])
    elif cmd == "status":
        status(bot)
    elif cmd == "routine":
        routine(bot)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    sys.modules["botrun"] = sys.modules["__main__"]  # orch imports this module: one copy, not two
import orch  # noqa: E402  (orch uses this module's pieces)

if __name__ == "__main__":
    main(sys.argv[1:])
