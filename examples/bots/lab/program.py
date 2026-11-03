"""The lab: the orchestrator as a bot, governed by this program. Each run is one generation: check the budget, review
what the experiment bots found, have Claude propose the next experiments, keep only the ones the hard rules allow and
its `promising` gate rates best, make them as bots, run them, and write the playbook.

What it learns, and from what: `promising` is an Ada model of which experiments turn out decisive, recorded from what
the experiments really found (never from its own guesses); the orchestrator's memory keeps every finding, so each
generation's proposals start from the last. Hard gates, in code: the budget (trials.py), at most ACTIVE experiments
at once and MAX_EXPERIMENTS in all, arms only from the lab's own strategies and models, two arms that differ in
exactly one thing.

Install it as `lab` (`glyphh bot install examples/bots/lab`): its experiments are bots beside it, exp_e1, exp_e2, ...,
in the bots' home, each run by the lab with the orchestrator's trust `autonomous` (they only run trials)."""

import json
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trials  # noqa: E402

ACTIVE = 3
MAX_EXPERIMENTS = 12
KINDS = ["bugfix", "implement", "multifile"]


def _experiments(ctx):
    return sorted(p for p in ctx.home.glob("exp_*") if (p / "experiment.json").exists())


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


def _settled(ctx, d):
    """The experiment's last run ended because Ada could already call every task."""
    runs = ctx.orchestrator.runner(d.name).store.recent(1)
    return bool(runs) and any("nothing left to learn" in line for line in runs[0]["log"] + [runs[0]["reason"]])


def review(ctx, inputs):
    """Each experiment's finding; a finished one is recorded once in `promising` (what it really found) and in the
    orchestrator's memory, and its bot stops."""
    found, active = [], []
    for d in _experiments(ctx):
        e = json.loads((d / "experiment.json").read_text())
        f = json.loads((d / "finding.json").read_text()) if (d / "finding.json").exists() else None
        done = (d / "reviewed").exists()
        finished = f and (f["call"] != "open") and (f["arms"][0]["n"] >= e["max_per_arm"] or _settled(ctx, d))
        if f:
            found.append(f)
        if finished and not done:
            ctx.gate("promising").record(promising_case(ctx, e), "decisive" if f["call"].startswith("decisive") else "null")
            ctx.orchestrator.remember(f"finding {e['id']}: {e['question']} -> {f['call']}; {f['arms']}",
                                      when="lab finding")
            (d / "reviewed").write_text(str(time.time()))
            ctx.log(f"finished {e['id']}: {f['call']}")
        elif not finished:
            active.append(e["id"])
    return {"findings": found, "active": active, "made": len(_experiments(ctx))}


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


def _signature(arms, kinds):
    return json.dumps(sorted(json.dumps(a, sort_keys=True) for a in arms)) + str(sorted(kinds))


def choose(ctx, proposals):
    """The proposals the hard rules allow, best rated by `promising` first; made as bots up to the caps."""
    text = proposals if isinstance(proposals, str) else json.dumps(proposals)
    m = re.search(r"\[.*\]", text, re.S)
    props = json.loads(m.group(0)) if m else []
    done = set()
    for d in _experiments(ctx):
        e = json.loads((d / "experiment.json").read_text())
        done.add(_signature(e["arms"], e["kinds"]))
    fresh = []
    for p in props:
        if _valid(p) and _signature(p.get("arms", []), p.get("kinds", [])) not in done:
            fresh.append(p)
        else:
            ctx.log(f"refused by the hard rules (or already run): {p.get('question', p)}")
    rated = sorted(((*_p_decisive(ctx, p), p) for p in fresh), key=lambda x: -x[0])
    active = len([d for d in _experiments(ctx) if not (d / "reviewed").exists()])
    room = min(ACTIVE - active, MAX_EXPERIMENTS - len(_experiments(ctx)))
    made = []
    for p_dec, unsure, p in rated[: max(room, 0)]:
        n = len(_experiments(ctx)) + 1
        slug = f"exp_e{n}"
        d = ctx.home / slug
        (d / "skills").mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / "experiment_program.py", d / "program.py")
        e = {"id": f"e{n}", "question": p["question"], "arms": p["arms"][:2], "kinds": p["kinds"], "max_per_arm": 12,
             "batch": 6}
        (d / "experiment.json").write_text(json.dumps(e, indent=1))
        (d / "bot.json").write_text(json.dumps(_bot_json(slug, e), indent=1))
        (d / "agent.md").write_text("---\nname: experiment\ndescription: unused: an experiment is all code\ntools: []\n"
                                    "---\n\nAn experiment bot: its program runs every step.\n")
        ctx.orchestrator.install(d, job=e["question"], trust="autonomous")
        made.append({"slug": slug, "question": e["question"], "p_decisive": round(p_dec, 2),
                     "by": "ada" if not unsure else "first come"})
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
    for d in _experiments(ctx):
        if (d / "reviewed").exists():
            continue
        ctx.log(f"running {d.name}")
        result = ctx.orchestrator.runner(d.name).run(routine=True)
        ran.append({"bot": d.name, "status": result.status, "reason": result.reason})
    return {"ran": ran, "spent": round(trials.spent(), 2)}


def report(ctx, inputs):
    rows = [s for s in trials.stats() if s["kind"]]
    exps = trials.ledger().execute("SELECT COUNT(DISTINCT exp) FROM trials").fetchone()[0]
    findings = [json.loads((d / "finding.json").read_text()) for d in _experiments(ctx) if (d / "finding.json").exists()]
    table = ["| kind | strategy | model | trials | pass % | $ / trial | s / trial |", "|---|---|---|---|---|---|---|"]
    table += [f"| {r['kind']} | {r['strategy']} | {r['model']} | {r['n']} | {r['pass_pct']} | {r['cost']:.3f} |"
              f" {r['seconds']} |" for r in rows]
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    (out / "measured.md").write_text("\n".join(table) + "\n")
    return {"table": "\n".join(table), "findings": findings, "spent": round(trials.spent(), 2), "experiments": exps}


def deliver(ctx, playbook):
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    (out / "playbook.md").write_text(playbook if isinstance(playbook, str) else json.dumps(playbook))
    return {"path": str(out / "playbook.md")}
