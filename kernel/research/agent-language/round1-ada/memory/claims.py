"""memory's claims, each a reproducible measurement (same shape as
lexicon/claims.py and world.py: measure(question, seed) -> answer word).

    python3 agents/memory/claims.py measure <subject> <relation> [k=v ...] --seed N
    python3 agents/memory/claims.py tell        # file them in the KB (author=memory)

A grader reproduces a claim with ITS OWN seed. For the kb_curve claims
the seed drives the whole simulated workload (which worker asks what,
every measurement draw), so agreement means the property belongs to
the KB design, not to one run.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "shared"))
sys.path.insert(0, str(HERE.parents[1] / "kernel_v1"))

from glyphh_kernel import Space, sim, symbol  # noqa: E402

Question = Tuple[str, str, Dict[str, str]]


def tiebreak_gap(n: int, seed: int) -> str:
    """Two n-attribute situations differing in ONE attribute: is sim
    higher by > 0.1 when the differing attribute sorts LAST than when it
    sorts FIRST?  yes | no   (odd n has no ties: expect no)"""
    sp = Space(seed=seed)
    base = {f"r{i}": f"x{seed}" for i in range(n)}
    first, last = dict(base), dict(base)
    first["r0"] = f"y{seed}"
    last[f"r{n - 1}"] = f"y{seed}"
    g = sp.encode(base)
    gap = sim(g, sp.encode(last)) - sim(g, sp.encode(first))
    return "yes" if gap > 0.1 else "no"


def kb_curve(prop: str, veto: str, hostile: str, seed: int) -> str:
    from demo_curve import run
    host = None if hostile == "none" else hostile
    drift = 400 if prop == "wrong_after_drift" else 10**9
    steps = 800 if prop == "wrong_after_drift" else 400
    rows, summary = run(steps=steps, drift=drift, veto=veto, hostile=host,
                        rng_seed=seed, verbose=False)
    last = rows[-1]
    if prop == "late_reflex_rate":       # bucket of the last window
        r = last["reflex_rate"]
        return "low" if r < 0.4 else "not_low"
    if prop == "late_reflex_acc":
        return "ge_0.95" if (last["reflex_acc"] or 0) >= 0.95 else "lt_0.95"
    if prop == "wrong_after_drift":      # wrong reflexes on flipped answers
        n = summary["wrong_reflexes_after_drift_on_changed"]
        return "le_25" if n <= 25 else "gt_25"
    raise KeyError(prop)


def measure(q: Question, seed: int) -> str:
    subject, relation, ctx = q
    if (subject, relation) == ("space_encode", "last_attr_differs_sims_higher"):
        return tiebreak_gap(int(ctx["n"]), seed)
    if subject == "kb_curve":
        return kb_curve(relation, ctx["veto_rule"], ctx["hostile"], seed)
    raise KeyError(q)


CLAIMS = [
    # (the space_encode tie-break claims were told as part of the canary
    #  set, see canaries.json)
    (("kb_curve", "late_reflex_rate", {"veto_rule": "trusted", "hostile": "none"}), "not_low"),
    (("kb_curve", "late_reflex_acc", {"veto_rule": "trusted", "hostile": "none"}), "ge_0.95"),
    (("kb_curve", "late_reflex_rate", {"veto_rule": "nearest", "hostile": "courier"}), "low"),
    (("kb_curve", "late_reflex_rate", {"veto_rule": "trusted", "hostile": "courier"}), "not_low"),
    (("kb_curve", "wrong_after_drift", {"veto_rule": "trusted", "hostile": "none"}), "le_25"),
    (("kb_curve", "wrong_after_drift", {"veto_rule": "parity", "hostile": "none"}), "gt_25"),
]


def _how(q: Question) -> str:
    s, r, ctx = q
    kv = " ".join(f"{k}={v}" for k, v in ctx.items())
    return f"python3 agents/memory/claims.py measure {s} {r} {kv} --seed <your seed>"


def tell_all(seed: int = 7) -> None:
    from knowledge import KB
    kb = KB()
    for q, claimed in CLAIMS:
        got = measure(q, seed)
        if got != claimed:
            print("NOT telling (my own run disagrees):", q, got, claimed)
            continue
        cid = kb.tell("memory", q[0], q[1], got, context=q[2], how=_how(q))
        print(cid, q, got)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "tell":
        tell_all()
    elif a and a[0] == "measure":
        seed = 7
        if "--seed" in a:
            i = a.index("--seed")
            seed = int(a[i + 1])
            a = a[:i] + a[i + 2:]
        ctx = dict(x.split("=", 1) for x in a[3:])
        print(measure((a[1], a[2], ctx), seed))
    else:
        print(__doc__)
