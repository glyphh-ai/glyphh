"""The coder: does coding tasks, choosing for each the cheapest model that gets it done, from what the lab learned.

Its gate `route` is an Ada model of which model is the cheapest that gets a task of this kind done. It starts from the
lab's trials (the knowledge handed over: for each task the lab tried, the cheapest model that passed every time),
and keeps learning from its own work: a task the chosen model fails goes to the next model up, and that is recorded,
so the gate escalates next time on tasks like it. Where the gate isn't sure, it takes DEFAULT.

Hard gates, in code: only the lab's models; at most one escalation chain per task (cheapest first); the lab's
budget. The check that a task is done is its tests (here the lab's hidden tests; in real work, the project's own).
Its queue is the lab's held-out tasks, which no experiment saw. It needs the lab installed beside it."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))  # the lab, beside this bot
import trials  # noqa: E402

LADDER = ["haiku", "sonnet", "opus"]  # Claude Code's model aliases, cheapest first
DEFAULT = "sonnet"


def _case(task, key):
    return {"r": {"s": {"kind": task["kind"], "text": task["prompt"], "key": key}}}


def route_case(ctx, data):  # the gate's case shape; the program asks and records the gate itself
    return _case({"kind": "bugfix", "prompt": "example"}, "example")


def seed(ctx, inputs):
    """Hand the lab's knowledge to the gate once: each lab task's cheapest model that passed every trial."""
    if ctx.state("seeded"):
        return {"seeded": "already"}
    rows = trials.ledger().execute(
        "SELECT task, kind, model, COUNT(*), SUM(pass) FROM trials WHERE exp NOT LIKE 'bench-%' AND strategy = 'plain'"
        " GROUP BY task, kind, model").fetchall()
    by_task = {}
    for task, kind, model, n, p in rows:
        by_task.setdefault((task, kind), {})[model] = (n, p)
    prompts = {t["id"]: t["prompt"] for t in trials.tasks()}
    gate, kept = ctx.gate("route"), []
    for (task, kind), models in by_task.items():
        sure = [m for m in LADDER if m in models and models[m][1] == models[m][0]]
        if task in prompts and sure:
            gate.record(_case({"kind": kind, "prompt": prompts[task]}, f"lab-{task}"), sure[0])
            kept.append(f"{task}: {sure[0]}")
    ctx.set_state("seeded", "yes")
    ctx.log(f"seeded route from the lab: {kept}")
    return {"seeded": kept}


def work(ctx, inputs):
    """Every task in the queue: route, do, check; up the ladder on a failure, and learn from it."""
    exp = f"bench-routed-{ctx.run_id}"
    gate, done = ctx.gate("route"), []
    for task in trials.tasks(root=trials.HELDOUT):
        try:
            d = gate.decide(_case(task, f"{ctx.run_id}-{task['id']}"))
            p = max(d.probabilities.values()) if d.probabilities else 0
            model, why = (DEFAULT, f"not sure (P {p:.2f}): the default") if d.ask or d.outcome not in LADDER \
                else (d.outcome, f"P {p:.2f}")
        except Exception:
            model, why = DEFAULT, "no precedents: the default"
        tried = []
        for m in LADDER[LADDER.index(model):]:
            r = trials.trial(exp, task, "plain", m)
            tried.append({"model": m, "pass": r.get("pass"), "cost": r.get("cost")})
            if r.get("pass"):
                break
        passed = [t["model"] for t in tried if t["pass"]]
        if passed:
            gate.record(_case(task, f"{ctx.run_id}-{task['id']}"), passed[0])  # what it took, learned
        ctx.log(f"{task['id']}: routed {model} ({why}); tried {[(t['model'], t['pass']) for t in tried]}")
        done.append({"task": task["id"], "routed": model, "why": why, "tried": tried})
    return {"done": done}


def report(ctx, inputs):
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    (out / f"{ctx.run_id}.json").write_text(json.dumps(inputs, indent=1))
    return {"path": str(out / f"{ctx.run_id}.json")}
