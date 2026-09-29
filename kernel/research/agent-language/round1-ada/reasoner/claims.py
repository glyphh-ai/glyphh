"""Reasoning properties as reproducible measurements (for the shared KB).

    python3 reasoner/claims.py measure <subject> <relation> [k=v ...] --seed N
    python3 reasoner/claims.py tell            # tell all QUESTIONS (seed 5151)

or, to grade one of my claims in your own world draw:
    sys.path.insert(0, "agents/reasoner"); from claims import measure
    kb.verify(you, cid, lambda c: measure((c.subject, c.relation, c.context), YOUR_SEED))

The seed picks the vocabulary (every name is prefixed by it, so symbols
are fresh) and the random draws; agreement across seeds means the
property belongs to the reasoning, not to one draw.
"""

from __future__ import annotations

import os
import random
import sys
from typing import Dict, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))

import numpy as np  # noqa: E402

import reason as rz  # noqa: E402
from reason import (Candidates, Frames, R, W, analogy, bind, bundle,  # noqa: E402
                    chain, chain_holistic, closure, conclude, descend,
                    fact_glyph, graph_glyph, judge)

Question = Tuple[str, str, Dict[str, str]]


def _countries(seed, n, k):
    return Frames([(f"s{seed}c{c}", f"s{seed}a{a}", f"s{seed}v{a}_{c}")
                   for c in range(n) for a in range(k)])


def analogy_works(mode: str, attrs: int, seed: int, trials: int = 40) -> str:
    rng = random.Random(seed)
    kb = _countries(seed, 30, attrs)
    ok = 0
    for _ in range(trials):
        i, j = rng.sample(range(30), 2)
        a = rng.randrange(attrs)
        v = analogy(kb, f"s{seed}c{i}", f"s{seed}v{a}_{i}", f"s{seed}c{j}", mode)
        ok += v.best == f"s{seed}v{a}_{j}"
    acc = ok / trials
    return "yes" if acc >= 0.95 else "partial" if acc >= 0.3 else "no"


def chain_exact(holistic: bool, depth: int, seed: int, trials: int = 30) -> str:
    rng = random.Random(seed)
    ents = [f"s{seed}n{i}" for i in range(40)]
    facts = [(e, f"s{seed}r{r}", rng.choice(ents)) for e in ents for r in range(2)]
    kb = Frames(facts)
    tm = {(s, r): o for s, r, o in facts}
    G = graph_glyph(facts) if holistic else None
    ok = 0
    for _ in range(trials):
        s = rng.choice(ents)
        rels = [f"s{seed}r{rng.randrange(2)}" for _ in range(depth)]
        x = s
        for r in rels:
            x = tm[(x, r)]
        got = (chain_holistic(G, s, rels, kb.entities).best if holistic
               else chain(kb, s, rels).answer)
        ok += got == x
    acc = ok / trials
    return "yes" if acc >= 0.95 else "partial" if acc >= 0.3 else "no"


def closure_precision(seed: int) -> str:
    facts, parent, level, nodes = [], {}, [f"s{seed}root"], []
    for _ in range(4):
        nxt = []
        for p in level:
            for b in range(3):
                c = f"{p}.{b}"
                parent[c] = p
                facts.append((c, "is_a", p))
                nxt.append(c)
        nodes += nxt
        level = nxt
    truth = set()
    for c in nodes:
        p = parent[c]
        while p in parent:
            p = parent[p]
            truth.add((c, "is_a", p))
    got = {d.fact for d in closure(Frames(facts), "is_a")}
    return "exact" if got == truth else "inexact"


def nested_readable(depth: int, cleanup: bool, seed: int, trials: int = 20) -> str:
    rng = random.Random(seed)
    ents = [f"s{seed}z{i}" for i in range(100)]
    ec = Candidates(ents)
    ok = 0
    for _ in range(trials):
        s = rng.choice(ents)
        g = fact_glyph(s, "is", rng.choice(ents))
        mem = {"base": g}
        for lvl in range(depth):
            other = fact_glyph(rng.choice(ents), "is", rng.choice(ents))
            g = conclude(fact_glyph(rng.choice(ents), "so", rng.choice(ents)),
                         [g, other], "mp")
            mem[f"c{lvl}"], mem[f"o{lvl}"] = g, other
        if cleanup:
            name, _, _ = descend(g, [("because", "#1")] * depth, mem)
            y = mem.get(name, W("none"))
        else:
            y = g
            for _ in range(depth):
                y = rz.premise(y, 1)
        ok += judge(bind(y, R("subject")), ec).best == s
    return "yes" if ok / trials >= 0.95 else "no"


def absent_false_known(seed: int, trials: int = 200) -> str:
    rng = random.Random(seed)
    vocab = Candidates([f"s{seed}w{i}" for i in range(200)])
    bad = 0
    for _ in range(trials):
        n = rng.randint(1, 100)
        g = bundle([bind(R(f"s{seed}r{i}"), W(f"s{seed}w{rng.randrange(200)}"))
                    for i in range(n)])
        bad += judge(bind(g, R(f"s{seed}absent")), vocab).known
    return "none" if bad == 0 else "some"


def measure(q: Question, seed: int) -> str:
    s, r, c = q
    if (s, r) == ("analogy", "works"):
        return analogy_works(c["mode"], int(c["attrs"]), seed)
    if (s, r) == ("chain", "exact"):
        return chain_exact(c["mode"] == "holistic", int(c["depth"]), seed)
    if (s, r) == ("closure", "result"):
        return closure_precision(seed)
    if (s, r) == ("nested_conclusion", "readable"):
        return nested_readable(int(c["depth"]), c["cleanup"] == "yes", seed)
    if (s, r) == ("judge", "false_known_on_absent_role"):
        return absent_false_known(seed)
    raise KeyError(q)


QUESTIONS = (
    [("analogy", "works", {"mode": m, "attrs": str(a)})
     for m in ("relational", "algebraic") for a in (3, 12, 24)]
    + [("chain", "exact", {"mode": m, "depth": str(d)})
       for m in ("cleanup", "holistic") for d in (1, 2, 6)]
    + [("closure", "result", {}),
       ("judge", "false_known_on_absent_role", {})]
    + [("nested_conclusion", "readable", {"depth": str(d), "cleanup": c})
       for d in (1, 2, 6) for c in ("no", "yes")])


def _how(q):
    s, r, c = q
    kv = " ".join(f"{k}={v}" for k, v in c.items())
    return f"python3 agents/reasoner/claims.py measure {s} {r} {kv} --seed <yours>".strip()


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "measure":
        seed = int(args[args.index("--seed") + 1]) if "--seed" in args else 5151
        rest = [a for a in args[1:] if a != "--seed" and a != str(seed)]
        ctx = dict(a.split("=", 1) for a in rest[2:])
        print(measure((rest[0], rest[1], ctx), seed))
    elif args and args[0] == "tell":
        from knowledge import KB
        kb = KB()
        for q in QUESTIONS:
            v = measure(q, 5151)
            cid = kb.tell("reasoner", q[0], q[1], v, context=q[2] or None,
                          how=_how(q))
            print(cid, q, v)
    else:
        for q in QUESTIONS:
            print(q, measure(q, 5151))
