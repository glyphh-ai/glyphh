"""The lab's trials: one coding task done by Claude one way, judged by tests it never saw.

The hard gates live here, in code no bot or gate can change: what an experiment may vary (STRATEGIES, MODELS, the
tasks), what a trial may cost and do (a fresh temp folder, Read/Edit/Write and only `python3 -m unittest`, a dollar
cap and a turn cap per trial), and the lab's whole budget (BUDGET_USD). Every trial is kept in ledger.sqlite, in the
lab's folder.

A task is a folder of tasks/ (or heldout/, the tasks no experiment sees): task.json `{"kind", "prompt"}`, src/ (the
code Claude works on) and hidden/test_hidden.py (the tests that judge it)."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LAB = Path(__file__).resolve().parent
TASKS = LAB / "tasks"
HELDOUT = LAB / "heldout"  # tasks no experiment ever sees
LEDGER = LAB / "ledger.sqlite"

STRATEGIES = {
    "plain": "{task}",
    "tests_first": "{task}\n\nFirst write a unittest test file that shows what is wrong or missing and run it with "
                   "`python3 -m unittest`; then change the code until your tests pass.",
    "plan_first": "{task}\n\nFirst write a short plan in PLAN.md (the cases to handle, the files to change, how you "
                  "will check it); then carry it out.",
    "edge_cases": "{task}\n\nBefore you change anything, list every edge case the description implies, then make "
                  "sure the code handles each one.",
}
MODELS = ["haiku", "sonnet", "opus"]  # Claude Code's model aliases
BUDGET_USD = 20.0  # the lab's whole spend, every experiment together
TRIAL_USD = 0.60  # one trial's cap
TRIAL_TURNS = 30
PARALLEL = 4


def tasks(kinds: list[str] | None = None, root: Path = TASKS) -> list[dict]:
    found = []
    for d in sorted(p for p in root.iterdir() if (p / "task.json").exists()):
        t = json.loads((d / "task.json").read_text())
        if not kinds or t["kind"] in kinds:
            found.append({"id": d.name, "root": str(root), **t})
    return found


def ledger() -> sqlite3.Connection:
    db = sqlite3.connect(LEDGER, timeout=30)
    db.execute("CREATE TABLE IF NOT EXISTS trials (exp TEXT, task TEXT, kind TEXT, strategy TEXT, model TEXT,"
               " pass INT, cost REAL, seconds REAL, turns INT, note TEXT, at REAL)")
    return db


def spent() -> float:
    return ledger().execute("SELECT COALESCE(SUM(cost), 0) FROM trials").fetchone()[0]


def trial(exp: str, task: dict, strategy: str, model: str) -> dict:
    if strategy not in STRATEGIES or model not in MODELS:
        raise ValueError(f"not an allowed arm: {strategy}/{model}")
    if spent() + TRIAL_USD > BUDGET_USD:
        return {"skipped": "the lab's budget is spent"}
    work = Path(tempfile.mkdtemp(prefix="lab-"))
    try:
        home = Path(task.get("root", TASKS)) / task["id"]
        shutil.copytree(home / "src", work, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        prompt = STRATEGIES[strategy].format(task=task["prompt"])
        cmd = ["claude", "-p", "--model", model, "--tools", "Read,Edit,Write,Bash",
               "--allowedTools", "Read Edit Write Bash(python3 -m unittest*)", "--permission-mode", "dontAsk",
               "--strict-mcp-config", "--setting-sources", "", "--max-budget-usd", str(TRIAL_USD),
               "--max-turns", str(TRIAL_TURNS), "--output-format", "json", "--no-session-persistence", prompt]
        t0 = time.time()
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=work, timeout=600)
        seconds = time.time() - t0
        try:
            out = json.loads(res.stdout)
        except ValueError:
            out = {}
        shutil.copy(home / "hidden" / "test_hidden.py", work / "test_hidden.py")
        judged = subprocess.run(["python3", "-m", "unittest", "test_hidden", "-q"], capture_output=True, text=True,
                                cwd=work, timeout=60)
        row = {"exp": exp, "task": task["id"], "kind": task["kind"], "strategy": strategy, "model": model,
               "pass": int(judged.returncode == 0), "cost": float(out.get("total_cost_usd") or 0),
               "seconds": round(seconds, 1), "turns": int(out.get("num_turns") or 0),
               "note": (judged.stderr.strip().splitlines() or [""])[-1][:200]}
    finally:
        shutil.rmtree(work, ignore_errors=True)
    db = ledger()
    db.execute("INSERT INTO trials VALUES (:exp, :task, :kind, :strategy, :model, :pass, :cost, :seconds, :turns,"
               " :note, :at)", {**row, "at": time.time()})
    db.commit()
    return row


def batch(exp: str, plan: list[tuple[dict, str, str]]) -> list[dict]:
    with ThreadPoolExecutor(PARALLEL) as pool:
        return list(pool.map(lambda p: trial(exp, *p), plan))


def stats(exp: str | None = None) -> list[dict]:
    """Pass rate, mean cost and time per arm (and kind), from the ledger."""
    q = ("SELECT kind, strategy, model, COUNT(*), SUM(pass), AVG(cost), AVG(seconds) FROM trials"
         + (" WHERE exp = ?" if exp else "") + " GROUP BY kind, strategy, model ORDER BY kind, strategy, model")
    rows = ledger().execute(q, (exp,) if exp else ()).fetchall()
    return [{"kind": k, "strategy": s, "model": m, "n": n, "pass_pct": round(100 * p / n), "cost": round(c, 4),
             "seconds": round(t, 1)} for k, s, m, n, p, c, t in rows]
