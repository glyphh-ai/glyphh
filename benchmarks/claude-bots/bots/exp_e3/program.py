"""An experiment bot's program: two arms (a way of working and a model) tried on the same tasks, judged by hidden
tests. Its gate `trial` is an Ada model of what passes: every trial the world answers is a precedent, and the program
asks it before each batch, so trials go where the outcome is still unknown and stop where it is known.

Hard gates (code, not learned): the lab's budget, at most `max_per_arm` trials an arm, only the lab's arms."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lab"))
import trials  # noqa: E402


def _exp(ctx):
    return json.loads((ctx.dir / "experiment.json").read_text())


def _arm(a):
    return f"{a['strategy']}/{a['model']}"


def _case(ctx, task, arm):
    return {"t": {"s": {"task": task["id"], "kind": task["kind"], "strategy": arm["strategy"], "model": arm["model"],
                        "run": f"{ctx.run_id}-{task['id']}-{_arm(arm)}"}}}


def trial_case(ctx, data):  # the gate's case shape, for the orchestrator's checks
    e = _exp(ctx)
    return _case(ctx, trials.tasks(e["kinds"])[0], e["arms"][0])


def budget(ctx, inputs):
    e = _exp(ctx)
    if trials.spent() + trials.TRIAL_USD * e["batch"] > trials.BUDGET_USD:
        return {"_end": "the lab's budget is spent"}
    done = trials.ledger().execute("SELECT COUNT(*) FROM trials WHERE exp = ?", (e["id"],)).fetchone()[0]
    if done >= e["max_per_arm"] * len(e["arms"]):
        return {"_end": "every trial this experiment may run is run"}
    return {"spent": round(trials.spent(), 2), "trials": done}


def pick(ctx, inputs):
    """The tasks whose outcome Ada can't yet call for either arm, fewest trials first."""
    e = _exp(ctx)
    db, gate = trials.ledger(), ctx.gate("trial")
    unknown = []
    for task in trials.tasks(e["kinds"]):
        n = min(db.execute("SELECT COUNT(*) FROM trials WHERE exp = ? AND task = ? AND strategy = ? AND model = ?",
                           (e["id"], task["id"], a["strategy"], a["model"])).fetchone()[0] for a in e["arms"])
        sure = n >= 2 and all(not _decide(gate, _case(ctx, task, a)) for a in e["arms"])
        if not sure:
            unknown.append((n, task))
    if not unknown:
        return {"_end": "Ada can call every task for both arms: nothing left to learn"}
    chosen = [t for _, t in sorted(unknown, key=lambda x: x[0])][: max(1, e["batch"] // len(e["arms"]))]
    ctx.log(f"{len(unknown)} tasks still unknown; trying {[t['id'] for t in chosen]}")
    return {"plan": [[t["id"], a] for t in chosen for a in e["arms"]]}


def _decide(gate, case):
    """Whether Ada still needs to see this one (True) or can call it (False)."""
    try:
        return gate.decide(case).ask
    except Exception:  # no precedents yet
        return True


def run_trials(ctx, inputs):
    e = _exp(ctx)
    by_id = {t["id"]: t for t in trials.tasks()}
    plan = [(by_id[tid], a["strategy"], a["model"]) for tid, a in inputs["plan"]]
    rows = trials.batch(e["id"], plan)
    gate = ctx.gate("trial")
    for (task, s, m), r in zip(plan, rows):
        if "skipped" in r:
            continue
        gate.record(_case(ctx, task, {"strategy": s, "model": m}), "pass" if r["pass"] else "fail")
        ctx.log(f"{task['id']} {s}/{m}: {'pass' if r['pass'] else 'FAIL'} ${r['cost']:.3f} {r['seconds']}s")
    return {"ran": len(rows)}


def verdict(ctx, inputs):
    """Each arm's record; decisive when one passes 25 points more, or costs half as much at the same pass rate."""
    e = _exp(ctx)
    db = trials.ledger()
    arms = []
    for a in e["arms"]:
        n, p, c, t = db.execute("SELECT COUNT(*), COALESCE(SUM(pass),0), COALESCE(AVG(cost),0), COALESCE(AVG(seconds),0)"
                                " FROM trials WHERE exp = ? AND strategy = ? AND model = ?",
                                (e["id"], a["strategy"], a["model"])).fetchone()
        arms.append({"arm": _arm(a), "n": n, "pass_pct": round(100 * p / n) if n else 0, "cost": round(c, 4),
                     "seconds": round(t, 1)})
    x, y = arms
    enough = min(x["n"], y["n"]) >= 6
    gap = x["pass_pct"] - y["pass_pct"]
    cheap = (abs(gap) <= 10 and min(x["cost"], y["cost"]) > 0 and max(x["cost"], y["cost"]) / min(x["cost"], y["cost"]) >= 2)
    if not enough:
        call = "open"
    elif abs(gap) >= 25:
        call = f"decisive: {(x if gap > 0 else y)['arm']} passes {abs(gap)} points more"
    elif cheap:
        low = x if x["cost"] < y["cost"] else y
        call = f"decisive: {low['arm']} matches at {max(x['cost'], y['cost']) / min(x['cost'], y['cost']):.1f}x less cost"
    else:
        call = "null: no difference worth having"
    finding = {"id": e["id"], "question": e["question"], "kinds": e["kinds"], "arms": arms, "call": call}
    (ctx.dir / "finding.json").write_text(json.dumps(finding, indent=1))
    ctx.log(f"verdict: {call} — {arms}")
    return finding
