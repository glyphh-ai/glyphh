"""The coder: does coding tasks, choosing for each the cheapest model that gets it done, from what the lab learned.

Its loop's `work` step is a ladder (SDK 3.9): the gate `route` is an Ada model of which model is the cheapest that
gets a task of this kind done; the runner starts each task on the rung the gate predicts (`start`, the middle one,
while it is unsure), `attempt` runs a trial, `passed` reads its hidden tests, a failure goes one rung up, and the
rung that passed is recorded, so the gate escalates next time on tasks like it. The gate starts from the lab's
trials (`seed`: for each task the lab tried, the cheapest model that passed every time).

Hard gates, in code: only the lab's models; one climb per task (cheapest first); the lab's budget (`trials.py`), and
each trial's cost reported with `ctx.spend`. The check that a task is done is its tests (here the lab's hidden tests;
in real work, the project's own). Its queue is the lab's held-out tasks, which no experiment saw. It needs the lab
installed beside it."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))  # the lab, beside this bot
import trials  # noqa: E402

LADDER = ["haiku", "sonnet", "opus"]  # Claude Code's model aliases, cheapest first: the route gate's outcomes


def _case(task, key):
    return {"r": {"s": {"kind": task["kind"], "text": task["prompt"], "key": key}}}


def route_case(ctx, task):
    """The route gate's case for one task."""
    return _case(task, f"{ctx.run_id}-{task['id']}")


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


def queue(ctx, inputs):
    """The tasks to do: the lab's held-out ones."""
    found = trials.tasks(root=trials.HELDOUT)
    if not found:
        return {"_end": "no task in the queue"}
    return {"items": found}


def attempt(ctx, rung, task):
    """One trial of the task on this rung's model, its cost counted against the bot's spend."""
    r = trials.trial(f"bench-routed-{ctx.run_id}", task, "plain", rung)
    if r.get("cost"):
        ctx.spend(r["cost"], f"trial {task['id']} {rung}")
    return r


def passed(ctx, rung, result, task):
    """Did it work: the task's hidden tests passed (a trial the budget skipped did not)."""
    return bool(result.get("pass")) and "skipped" not in result


def report(ctx, inputs):
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    (out / f"{ctx.run_id}.json").write_text(json.dumps(inputs, indent=1, default=str))
    return {"path": str(out / f"{ctx.run_id}.json")}
