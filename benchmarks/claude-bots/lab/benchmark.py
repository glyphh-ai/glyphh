"""The benchmark: does what the lab learned save money on work it never saw?

Five held-out tasks (lab/heldout: two bugfixes, two from-scratch implementations, one multi-file change), each done
the plain way, judged by hidden tests, `REPS` times by each of three arms:

  always-opus    every task to Opus
  always-sonnet  every task to Sonnet (Claude Code's default)
  routed         the coder bot: its `route` gate picks the model from what the lab learned, escalates on a failure,
                 and learns from each task it does (rep 2 starts from what rep 1 taught it)

Pass rate counts a task done only if its hidden tests pass; the routed arm's cost includes every escalation.
Writes lab/benchmark.json and lab/benchmark.md."""

import json
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parent
ROOT = LAB.parent
sys.path.insert(0, str(LAB))
import trials  # noqa: E402

REPS = 2


def run():
    held = trials.tasks(root=trials.HELDOUT)
    for rep in range(1, REPS + 1):
        for model in ("opus", "sonnet"):
            print(f"rep {rep}: always-{model}", flush=True)
            trials.batch(f"bench-{model}-{rep}", [(t, "plain", model) for t in held])
        print(f"rep {rep}: routed", flush=True)
        state = __import__("sqlite3").connect(ROOT / "bots" / "coder" / "runs.sqlite")
        state.execute("CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT)")
        state.execute("INSERT OR REPLACE INTO state VALUES ('rep', ?)", (str(rep),))
        state.commit()
        subprocess.run([sys.executable, str(ROOT / "botrun.py"), "run", "coder", "--routine"], check=False)


def results():
    db = trials.ledger()
    arms = {}
    for name, like in (("always-opus", "bench-opus-%"), ("always-sonnet", "bench-sonnet-%"), ("routed", "bench-routed-%")):
        rows = db.execute("SELECT exp, task, model, pass, cost, seconds FROM trials WHERE exp LIKE ?", (like,)).fetchall()
        per = {}
        for exp, task, model, p, c, s in rows:
            k = (exp, task)
            got = per.setdefault(k, {"pass": 0, "cost": 0.0, "seconds": 0.0, "models": []})
            got["pass"] = max(got["pass"], p)
            got["cost"] += c
            got["seconds"] += s
            got["models"].append(model)
        n = len(per)
        arms[name] = {"tasks": n, "passed": sum(v["pass"] for v in per.values()),
                      "cost": round(sum(v["cost"] for v in per.values()), 4),
                      "seconds": round(sum(v["seconds"] for v in per.values()), 1),
                      "per_task": {f"{e}:{t}": v for (e, t), v in sorted(per.items())}}
    base = arms["always-opus"]["cost"] or 1
    for a in arms.values():
        a["pass_pct"] = round(100 * a["passed"] / a["tasks"]) if a["tasks"] else 0
        a["cost_vs_opus"] = round(a["cost"] / base, 3)
    (LAB / "benchmark.json").write_text(json.dumps(arms, indent=1))
    lines = ["| arm | tasks | passed | pass % | total $ | $ vs always-opus | total s |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {k} | {a['tasks']} | {a['passed']} | {a['pass_pct']} | {a['cost']:.3f} | {a['cost_vs_opus']:.2f}x | {a['seconds']} |"
              for k, a in arms.items()]
    (LAB / "benchmark.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return arms


if __name__ == "__main__":
    if "--results" not in sys.argv:
        run()
    results()
