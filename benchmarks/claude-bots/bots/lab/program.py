"""The lab: the orchestrator as a bot, governed by this program. Each run is one generation: check the budget, review
what the experiment bots found, have Claude propose the next experiments, keep only the ones the hard rules allow and
its `promising` gate rates best, make them as bots, run them, and write the playbook.

What it learns, and from what: `promising` is an Ada model of which experiments turn out decisive, recorded from what
the experiments really found (never from its own guesses); the orchestrator's memory keeps every finding, so each
generation's proposals start from the last. Hard gates, in code: the budget (lab/trials.py), at most ACTIVE
experiments at once and MAX_EXPERIMENTS in all, arms only from the lab's own strategies and models, two arms that
differ in exactly one thing."""

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "lab"))
import trials  # noqa: E402

ACTIVE = 3
MAX_EXPERIMENTS = 12
KINDS = ["bugfix", "implement", "multifile"]


def _experiments():
    return sorted(p for p in (ROOT / "bots").glob("exp_*") if (p / "experiment.json").exists())


def budget(ctx, inputs):
    left = trials.BUDGET_USD - trials.spent()
    if left < trials.TRIAL_USD * 6:
        return {"_end": f"the lab's budget is spent (${trials.spent():.2f} of ${trials.BUDGET_USD:.0f})"}
    return {"spent": round(trials.spent(), 2), "left": round(left, 2)}


def promising_case(ctx, e):
    a, b = e["arms"]
    varies = "strategy" if a["model"] == b["model"] else "model"
    return {"e": {"s": {"question": e["question"], "varies": varies, "kinds": ",".join(sorted(e["kinds"])),
                        "arm_a": f"{a['strategy']}/{a['model']}", "arm_b": f"{b['strategy']}/{b['model']}",
                        "id": e.get("id", "proposal")}}}


def review(ctx, inputs):
    """Each experiment's finding; a finished one is recorded once in `promising` (what it really found) and in the
    orchestrator's memory, and its bot stops."""
    import botrun

    found, active = [], []
    for d in _experiments():
        e = json.loads((d / "experiment.json").read_text())
        f = json.loads((d / "finding.json").read_text()) if (d / "finding.json").exists() else None
        done = (d / "reviewed").exists()
        finished = f and (f["call"] != "open") and (f["arms"][0]["n"] >= e["max_per_arm"] or _settled(d))
        if f:
            found.append(f)
        if finished and not done:
            ctx.gate("promising").record(promising_case(ctx, e), "decisive" if f["call"].startswith("decisive") else "null")
            botrun.remember(botrun.ada(), "orch-memory", "memory", f"finding {e['id']}: {e['question']} -> {f['call']}; "
                            f"{f['arms']}", when="lab finding")
            (d / "reviewed").write_text(str(time.time()))
            ctx.log(f"finished {e['id']}: {f['call']}")
        elif not finished:
            active.append(e["id"])
    return {"findings": found, "active": active, "made": len(_experiments())}


def _settled(d):
    """The experiment's last run ended because Ada could already call every task."""
    import sqlite3

    rows = sqlite3.connect(d / "runs.sqlite").execute("SELECT log FROM runs ORDER BY started DESC LIMIT 1").fetchall()
    return bool(rows) and "nothing left to learn" in (rows[0][0] or "")


def _valid(p):
    a, b = p.get("arms", [{}, {}])[:2] if len(p.get("arms", [])) == 2 else ({}, {})
    ok_arm = lambda x: x.get("strategy") in trials.STRATEGIES and x.get("model") in trials.MODELS  # noqa: E731
    one = (a.get("strategy") == b.get("strategy")) != (a.get("model") == b.get("model"))
    kinds = p.get("kinds") and all(k in KINDS for k in p["kinds"])
    return bool(ok_arm(a) and ok_arm(b) and one and kinds and p.get("question"))


def _p_decisive(ctx, p):
    try:
        d = ctx.gate("promising").decide(promising_case(ctx, p))
        return d.probabilities.get("decisive", 0.5), d.ask
    except Exception:  # no precedents yet: every proposal alike
        return 0.5, True


def choose(ctx, proposals):
    """The proposals the hard rules allow, best rated by `promising` first; made as bots up to the caps."""
    import botrun

    text = proposals if isinstance(proposals, str) else json.dumps(proposals)
    m = re.search(r"\[.*\]", text, re.S)
    props = json.loads(m.group(0)) if m else []
    done = {json.dumps(sorted([json.dumps(a, sort_keys=True) for a in json.loads((d / "experiment.json").read_text())["arms"]]))
            + str(sorted(json.loads((d / "experiment.json").read_text())["kinds"])) for d in _experiments()}
    fresh = []
    for p in props:
        sig = json.dumps(sorted([json.dumps(a, sort_keys=True) for a in p.get("arms", [])])) + str(sorted(p.get("kinds", [])))
        if _valid(p) and sig not in done:
            fresh.append(p)
        else:
            ctx.log(f"refused by the hard rules (or already run): {p.get('question', p)}")
    rated = sorted(((*_p_decisive(ctx, p), p) for p in fresh), key=lambda x: -x[0])
    active = len([d for d in _experiments() if not (d / "reviewed").exists()])
    room = min(ACTIVE - active, MAX_EXPERIMENTS - len(_experiments()))
    made = []
    for p_dec, unsure, p in rated[: max(room, 0)]:
        n = len(_experiments()) + 1
        slug = f"exp_e{n}"
        d = ROOT / "bots" / slug
        (d / "skills").mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "lab" / "experiment_program.py", d / "program.py")
        e = {"id": f"e{n}", "question": p["question"], "arms": p["arms"][:2], "kinds": p["kinds"], "max_per_arm": 12, "batch": 6}
        (d / "experiment.json").write_text(json.dumps(e, indent=1))
        (d / "bot.json").write_text(json.dumps(_bot_json(slug, e), indent=1))
        (d / "agent.md").write_text("---\nname: experiment\ndescription: unused: an experiment is all code\ntools: []\n"
                                    "model: haiku\n---\n\nAn experiment bot: its program runs every step.\n")
        botrun.install(botrun.Bot(slug))
        botrun.orch.db().execute("INSERT OR REPLACE INTO bots VALUES (?, ?, ?, 'autonomous', 'keep')",
                                 (slug, e["question"], time.time())).connection.commit()
        made.append({"slug": slug, "question": e["question"], "p_decisive": round(p_dec, 2), "by": "ada" if not unsure else "first come"})
        ctx.log(f"made {slug}: {e['question']} (P decisive {p_dec:.2f})")
    return {"made": made, "proposed": len(props), "allowed": len(fresh)}


def _bot_json(slug, e):
    return {"slug": slug, "name": f"Experiment {e['id']}", "summary": e["question"], "version": 1, "agent": "agent.md",
            "reads_glyphh": False, "touches": "read_only", "hosts": [], "seed": {},
            "gates": {"trial": {"case": "trial_case", "outcomes": ["pass", "fail"], "spec": {
                "name": "trial", "layers": [{"name": "t", "segments": [{"name": "s", "roles": [
                    {"name": "task"}, {"name": "kind"}, {"name": "strategy"}, {"name": "model"},
                    {"name": "run", "key_part": True, "similarity_weight": 0}]}]}],
                "output": {"costs": {"pass": {"fail": 1}, "fail": {"pass": 1}}, "ask_below": 0.8}}}},
            "loop": [{"id": "budget", "run": "budget"}, {"id": "pick", "run": "pick"},
                     {"id": "trials", "run": "run_trials", "input": "$pick"}, {"id": "verdict", "run": "verdict"}],
            "limits": {"seconds": 1800}}


def run_all(ctx, inputs):
    ran = []
    for d in _experiments():
        if (d / "reviewed").exists():
            continue
        ctx.log(f"running {d.name}")
        res = subprocess.run([sys.executable, str(ROOT / "botrun.py"), "run", d.name, "--routine"], capture_output=True,
                             text=True, timeout=3600)
        ran.append({"bot": d.name, "said": res.stdout.strip().splitlines()[-1:] if res.stdout else res.stderr[-300:]})
    return {"ran": ran, "spent": round(trials.spent(), 2)}


def report(ctx, inputs):
    rows = [s for s in trials.stats() if s["kind"]]
    exp_rows = [r for r in trials.ledger().execute("SELECT exp FROM trials GROUP BY exp")]
    findings = [json.loads((d / "finding.json").read_text()) for d in _experiments() if (d / "finding.json").exists()]
    table = ["| kind | strategy | model | trials | pass % | $ / trial | s / trial |", "|---|---|---|---|---|---|---|"]
    table += [f"| {r['kind']} | {r['strategy']} | {r['model']} | {r['n']} | {r['pass_pct']} | {r['cost']:.3f} | {r['seconds']} |"
              for r in rows]
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    (out / "measured.md").write_text("\n".join(table) + "\n")
    return {"table": "\n".join(table), "findings": findings, "spent": round(trials.spent(), 2), "experiments": len(exp_rows)}


def deliver(ctx, playbook):
    out = ctx.dir / "out"
    (out / "playbook.md").write_text(playbook if isinstance(playbook, str) else json.dumps(playbook))
    return {"path": str(out / "playbook.md")}
