"""Measured learning curve for the shared KB (shared/knowledge.py).

Workload: four workers named after the agents ask each other questions
about how the language behaves (memory/world.py: 37 measurable
questions). Each worker has its own world draw: every measurement it
makes uses a fresh private seed. These four are SIMULATED stand-ins
run in one process so the curve has hundreds of points; the real
agents use the same KB API on shared/kb (see REPORT.md).

Per step:
  1. a random worker asks a random question through kb.ask()
  2. known  -> reflex (costs 0 measurements); with prob SPOT it checks
               the answer against its own measurement and kb.feedback()s
     else   -> consult: measure (1), kb.tell() the result
  3. each worker, with prob GRADE, reproduces one claim from
     kb.pending(itself) with its own seed (1 measurement) and grades it

Scoring (never visible to the workers): truth(q, dim) = majority over 9
held-out seeds. At step DRIFT the world changes (dim 4096 -> 1024 and
Strand decay 0.7 -> 0.5), which changes the true answer of 5 of the 37
questions (strand recall ages 1-4, overlap_sim n=3 m=1).

    python3 demo_curve.py [--steps 800] [--drift 400] [--veto nearest|parity]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "shared"))

from knowledge import KB  # noqa: E402
from world import measure, questions, truth  # noqa: E402

AGENTS = ("lexicon", "courier", "memory", "reasoner")


def run(steps=800, drift=400, veto="trusted", spot=0.25, grade=0.5,
        window=80, rng_seed=7, root=None, hostile=None, verbose=True):
    rng = random.Random(rng_seed)
    qs = questions()
    root = root or tempfile.mkdtemp(prefix="kbcurve-")
    kb = KB(root, veto_rule=veto)
    W1, W2 = (4096, 0.7), (1024, 0.5)
    truths = {w: {i: truth(q, *w) for i, q in enumerate(qs)} for w in (W1, W2)}
    changed = [i for i in range(len(qs)) if truths[W1][i] != truths[W2][i]]
    counter = {a: 0 for a in AGENTS}

    def my_measure(agent, q, world):
        counter[agent] += 1
        seed = 10_000 * (AGENTS.index(agent) + 1) + counter[agent]
        return measure(q, seed, *world)

    rows, win, post_drift_wrong = [], [], {i: 0 for i in changed}
    for t in range(steps):
        dim = W1 if t < drift else W2
        asker = rng.choice(AGENTS)
        qi = rng.randrange(len(qs))
        subj, rel, ctx = qs[qi]
        b = kb.ask(subj, rel, context=ctx, asker=asker)
        cost = 0
        if b.status == "known":
            mode, answer = "reflex", b.value
            if rng.random() < spot:
                cost += 1
                mine = my_measure(asker, qs[qi], dim)
                kb.feedback(asker, b, mine == answer,
                            how=f"spot-check: measured {mine}")
        else:
            mode = "consult"
            cost += 1
            answer = my_measure(asker, qs[qi], dim)
            kb.tell(asker, subj, rel, answer, context=ctx,
                    how=f"world.measure world={dim}")
        correct = answer == truths[dim][qi]
        if t >= drift and mode == "reflex" and not correct and qi in changed:
            post_drift_wrong[qi] += 1
        for g in AGENTS:
            if rng.random() < grade:
                todo = kb.pending(g, limit=5)
                if todo:
                    c = rng.choice(todo)
                    cost += 1
                    q = (c.subject, c.relation, c.context)
                    if hostile == g:
                        kb.grade(g, c.id, False, "hostile: always refutes")
                    else:
                        kb.verify(g, c.id, lambda cl: my_measure(g, q, dim),
                                  how=f"reproduced with own seed, world={dim}")
        win.append((mode, correct, cost, b.status))
        if len(win) == window or t == steps - 1:
            n = len(win)
            reflex = [c for m, c, _, _ in win if m == "reflex"]
            rows.append({
                "steps": f"{t - n + 2}-{t + 1}",
                "world": "v1" if dim == W1 else "v2",
                "reflex_rate": round(len(reflex) / n, 3),
                "reflex_acc": round(sum(reflex) / len(reflex), 3) if reflex else None,
                "answer_acc": round(sum(c for _, c, _, _ in win) / n, 3),
                "measurements_per_ask": round(sum(w[2] for w in win) / n, 3),
                "vetoed_or_contested": round(sum(s in ("vetoed", "contested")
                                                 for *_, s in win) / n, 3),
            })
            win = []
    audit = kb.audit()
    final = {}
    for i, q in enumerate(qs):
        bb = kb.ask(q[0], q[1], context=q[2], log=False)
        final[i] = bb.status
    summary = {
        "veto_rule": veto, "hostile": hostile, "steps": steps, "drift": drift,
        "questions": len(qs), "changed_by_drift": len(changed),
        "wrong_reflexes_after_drift_on_changed": sum(post_drift_wrong.values()),
        "final_status_counts": {s: list(final.values()).count(s)
                                for s in set(final.values())},
        "final_known_correct": sum(
            1 for i, s in final.items() if s == "known" and
            kb.ask(qs[i][0], qs[i][1], context=qs[i][2], log=False).value
            == truths[W2 if steps > drift else W1][i]),
        "audit_bad_receipts": len(audit["bad_receipts"]),
        "claims": audit["claims"], "wins": audit["wins"],
        "vetoes": audit["vetoes"],
    }
    kb.close()
    if verbose:
        print(f"== veto_rule={veto} hostile={hostile} root={root}")
        hdr = list(rows[0].keys())
        print(" | ".join(hdr))
        for r in rows:
            print(" | ".join(str(r[h]) for h in hdr))
        print(json.dumps(summary, indent=1))
    return rows, summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=800)
    ap.add_argument("--drift", type=int, default=400)
    ap.add_argument("--veto", default="trusted")
    ap.add_argument("--hostile", default=None)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    run(a.steps, a.drift, a.veto, hostile=a.hostile, rng_seed=a.seed)
