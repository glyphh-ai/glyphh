"""Measurements for shared/reason.py. Run: python3 reasoner/bench.py [--quick]

Every number in reasoner/REPORT.md comes from this file's output.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))

import reason as rz  # noqa: E402
from reason import (Candidates, Frames, R, W, abstract, analogy, bind,  # noqa
                    bundle, chain, chain_holistic, classify, closure, conclude,
                    fact_glyph, graph_glyph, judge, sim, typical)

QUICK = "--quick" in sys.argv


def banner(t):
    print("\n== " + t)


# E1 ─ is judge()'s confidence calibrated? ─────────────────────────
def e1_calibration(trials=3000):
    banner("E1 calibration of judge(): unbind a role from a bundle of n pairs")
    rng = random.Random(1)
    V = 300
    vocab = [f"e1w{i}" for i in range(V)]
    cands = Candidates(vocab)
    roles = [f"e1r{i}" for i in range(400)]
    rows = []  # (conf, correct, present)
    for t in range(trials):
        n = int(round(np.exp(rng.uniform(0, np.log(400)))))
        rs = rng.sample(roles, n)
        vals = [rng.choice(vocab) for _ in rs]
        g = bundle([bind(R(r), W(v)) for r, v in zip(rs, vals)])
        present = rng.random() < 0.75
        if present:
            j = rng.randrange(n)
            v = judge(bind(g, R(rs[j])), cands)
            rows.append((v.conf, v.best == vals[j], True, v.known, n))
        else:
            other = rng.choice([r for r in roles if r not in rs])
            v = judge(bind(g, R(other)), cands)
            rows.append((v.conf, False, False, v.known, n))
    bins = [0, .1, .3, .5, .7, .9, .99, 1.0001]
    print(" conf bin      N   P(best correct)  [present queries]")
    ece, tot = 0.0, 0
    pres = [r for r in rows if r[2]]
    for lo, hi in zip(bins, bins[1:]):
        b = [r for r in pres if lo <= r[0] < hi]
        if not b:
            continue
        acc = np.mean([r[1] for r in b])
        mc = np.mean([r[0] for r in b])
        ece += len(b) * abs(acc - mc)
        tot += len(b)
        print(f" [{lo:.2f},{min(hi,1):.2f})  {len(b):5d}   acc={acc:.3f}  mean_conf={mc:.3f}")
    ece /= tot
    known = [r for r in rows if r[3]]
    prec = np.mean([r[1] for r in known])
    absent = [r for r in rows if not r[2]]
    false_known = np.mean([r[3] for r in absent])
    cov = np.mean([r[3] for r in pres])
    acc_all = np.mean([r[1] for r in pres])
    print(f" ECE(present)={ece:.3f}  precision of 'known'={prec:.4f} "
          f"coverage(present)={cov:.3f}  raw best-acc(present)={acc_all:.3f}")
    print(f" absent-role queries: false 'known' rate={false_known:.4f} "
          f"(n={len(absent)})")
    # the threshold sweep: precision / coverage of 'known'
    print(" threshold sweep: known_at -> precision, coverage(present), false-known(absent)")
    for th in (0.5, 0.7, 0.9, 0.99):
        k = [r for r in rows if r[0] >= th]
        p = np.mean([r[1] for r in k]) if k else float("nan")
        c = np.mean([r[0] >= th for r in pres])
        f = np.mean([r[0] >= th for r in absent])
        print(f"   {th:.2f} -> {p:.4f}, {c:.3f}, {f:.4f}")
    # capacity: best-acc by n
    print(" best-acc / known-rate by bundle size n:")
    for lo, hi in ((1, 20), (20, 60), (60, 120), (120, 250), (250, 401)):
        b = [r for r in pres if lo <= r[4] < hi]
        print(f"   n in [{lo},{hi}): acc={np.mean([r[1] for r in b]):.3f} "
              f"known={np.mean([r[3] for r in b]):.3f} (N={len(b)})")
    return {"ece": ece, "precision_known": prec, "false_known_absent": false_known,
            "coverage": cov}


# E2 ─ analogy ────────────────────────────────────────────────────
def country_kb(n_countries, n_attrs, rng):
    attrs = [f"attr{i}" for i in range(n_attrs)]
    facts = []
    for c in range(n_countries):
        for a in attrs:
            facts.append((f"country{c}", a, f"v_{a}_{c}"))
    return Frames(facts), attrs


def e2_analogy(trials=200):
    banner("E2 analogy a:b::c:?  (a=country_i, b=its value for attr, c=country_j)")
    rng = random.Random(2)
    out = {}
    print(" attrs/frame  relational acc  known   algebraic acc  known   (40 countries)")
    for k in (3, 6, 12, 24, 48):
        kb, attrs = country_kb(40, k, rng)
        res = {"relational": [], "algebraic": []}
        for _ in range(trials if not QUICK else 50):
            i, j = rng.sample(range(40), 2)
            a = rng.choice(attrs)
            truth = f"v_{a}_{j}"
            for mode in res:
                v = analogy(kb, f"country{i}", f"v_{a}_{i}", f"country{j}", mode)
                res[mode].append((v.best == truth, v.known,
                                  v.known and v.answer == truth))
        line = f" {k:5d}      "
        for mode in ("relational", "algebraic"):
            r = res[mode]
            acc = np.mean([x[0] for x in r])
            kn = np.mean([x[1] for x in r])
            pk = np.mean([x[2] for x in r if x[1]]) if any(x[1] for x in r) else float("nan")
            out[(k, mode)] = (acc, kn, pk)
            line += f"    {acc:.3f}   {kn:.3f} (prec {pk:.3f})"
        print(line)
    return out


# E3 ─ chained inference vs depth ───────────────────────────────────
def e3_chain(trials=150):
    banner("E3 multi-hop inference: accuracy vs depth")
    rng = random.Random(3)
    E = 60
    ents = [f"n{i}" for i in range(E)]

    def graph(nrel):
        facts = [(e, f"rel{r}", rng.choice(ents)) for e in ents for r in range(nrel)]
        return Frames(facts)

    res = {}
    for nrel, label in ((2, "small frames (2 relations)"),
                        (180, "big frames (180 relations, per-hop noisy)")):
        kb = graph(nrel)
        truth_map = {(s, r): o for s, r, o in kb.facts}
        G = graph_glyph(kb.facts) if nrel == 2 else None
        ec = kb.entities
        print(f" {label}:")
        print("   depth  clean-hop acc  known  prec(known)  mean_conf" +
              ("   holistic acc" if G is not None else ""))
        for d in (1, 2, 3, 4, 6, 8):
            rows, hol = [], []
            for _ in range(trials if not QUICK else 40):
                s = rng.choice(ents)
                rels = [f"rel{rng.randrange(nrel)}" for _ in range(d)]
                x = s
                for r in rels:
                    x = truth_map[(x, r)]
                c = chain(kb, s, rels)
                rows.append((c.path[-1] == x, c.known, c.conf))
                if G is not None:
                    hol.append(chain_holistic(G, s, rels, ec).best == x)
            acc = np.mean([r[0] for r in rows])
            kn = np.mean([r[1] for r in rows])
            pk = (np.mean([r[0] for r in rows if r[1]])
                  if any(r[1] for r in rows) else float("nan"))
            mc = np.mean([r[2] for r in rows])
            res[(nrel, d)] = (acc, kn, pk, mc, np.mean(hol) if hol else None)
            print(f"   {d:5d}  {acc:12.3f}  {kn:5.3f}  {pk:10.3f}  {mc:9.3f}" +
                  (f"   {np.mean(hol):12.3f}" if hol else ""))
    return res


# E4 ─ transitive closure produces new facts ───────────────────────
def e4_closure():
    banner("E4 transitive closure over is_a (tree depth 5, branching 3) + distractor attrs")
    out = {}
    for n_extra in (0, 8, 40):
        rng = random.Random(4)
        facts, parent = [], {}
        level = ["root"]
        nodes = []
        for depth in range(5):
            nxt = []
            for p in level:
                for b in range(3):
                    c = f"{p}.{b}"
                    parent[c] = p
                    facts.append((c, "is_a", p))
                    nxt.append(c)
            nodes += nxt
            level = nxt
        for c in nodes:  # distractor facts that crowd each frame
            for a in range(n_extra):
                facts.append((c, f"has{a}", f"x{rng.randrange(50)}"))
        kb = Frames(facts)
        truth = set()
        for c in nodes:
            p, d = parent[c], 1
            while p in parent:
                p = parent[p]
                d += 1
                truth.add((c, "is_a", p))
        t0 = time.time()
        der = closure(kb, "is_a")
        got = {x.fact for x in der}
        tp = len(got & truth)
        prec = tp / max(len(got), 1)
        rec = tp / len(truth)
        out[n_extra] = (prec, rec, len(got), len(truth))
        print(f" distractor attrs/frame={n_extra:3d}: derived {len(got)} new facts, "
              f"true {len(truth)}; precision={prec:.3f} recall={rec:.3f} "
              f"({time.time()-t0:.1f}s)")
    return out


# E5 ─ abstraction: the gist of many cases ─────────────────────────
def e5_abstraction(trials=100):
    banner("E5 abstraction: prototype = bundle(cases); typical() and classify()")
    rng = random.Random(5)
    C, A = 6, 8
    attrs = [f"a{i}" for i in range(A)]
    vals = [f"val{i}" for i in range(40)]
    cands = Candidates(vals)
    protos_true = {f"cat{c}": {a: rng.choice(vals) for a in attrs} for c in range(C)}

    def instance(cat, p):
        return {a: (v if rng.random() > p else rng.choice(vals))
                for a, v in protos_true[cat].items()}

    def enc(inst):
        return bundle([bind(R(a), W(v)) for a, v in sorted(inst.items())])

    out = {}
    print("  p(noise)  cases  typical-acc  classify-acc(held-out)  mean-sim-to-instance")
    for p in (0.2, 0.5):
        for m in (1, 3, 9, 27):
            protos = {}
            for cat in protos_true:
                protos[cat] = abstract([enc(instance(cat, p)) for _ in range(m)])
            typ = np.mean([typical(protos[c], a, cands).best == protos_true[c][a]
                           for c in protos for a in attrs])
            cls, sims = [], []
            for _ in range(trials if not QUICK else 30):
                cat = rng.choice(list(protos_true))
                g = enc(instance(cat, p))
                v = classify(g, protos)
                cls.append(v.best == cat)
                sims.append(sim(g, protos[cat]))
            out[(p, m)] = (typ, np.mean(cls))
            print(f"  {p:6.1f}  {m:5d}  {typ:10.3f}  {np.mean(cls):20.3f}  "
                  f"{np.mean(sims):18.3f}")
    return out


# E6 ─ conclusions nested in conclusions ────────────────────────────
def e6_nesting():
    banner("E6 composition: a conclusion whose premise is a conclusion, depth d")
    rng = random.Random(6)
    ents = [f"z{i}" for i in range(200)]
    ec = Candidates(ents)
    out = {}
    print("  depth  raw sim(subject)  raw acc   cleanup-memory acc  (no path exclusion)")
    for d in (1, 2, 3, 4, 6, 10):
        raw, acc, accm, accn = [], [], [], []
        for _ in range(60 if not QUICK else 20):
            s = rng.choice(ents)
            base = fact_glyph(s, "is", rng.choice(ents))
            memory = {"base": base}
            g = base
            for lvl in range(d):
                other = fact_glyph(rng.choice(ents), "is", rng.choice(ents))
                g = conclude(fact_glyph(rng.choice(ents), "so", rng.choice(ents)),
                             [g, other], "modus_ponens")
                memory[f"c{lvl}"] = g
                memory[f"o{lvl}"] = other
            # raw: walk down premise #1 d times, no cleanup
            x = g
            for _ in range(d):
                x = rz.premise(x, 1)
            xs = bind(x, R("subject"))
            raw.append(sim(xs, W(s)))
            acc.append(judge(xs, ec).best == s)
            # with cleanup memory: after each unslot, snap to the nearest
            # glyph we have seen (lexicon's define()/concept mechanism)
            for excl, lst in ((True, accm), (False, accn)):
                name, _, _ = rz.descend(g, [("because", "#1")] * d, memory,
                                        exclude_path=excl)
                y = memory.get(name, W("none"))
                lst.append(judge(bind(y, R("subject")), ec).best == s)
        out[d] = (np.mean(raw), np.mean(acc), np.mean(accm), np.mean(accn))
        print(f"  {d:5d}  {np.mean(raw):15.3f}  {np.mean(acc):7.3f}  {np.mean(accm):12.3f}"
              f"        {np.mean(accn):.3f}")
    return out


# E7 ─ ordinal inference on memory's world ──────────────────────────
def e7_ordinal(trials=40, rng_seed=7):
    banner("E7 ordinal inference on memory/world.py: predict UNMEASURED questions")
    sys.path.insert(0, os.path.join(HERE, "..", "memory"))
    import world
    fams = {
        ("bundle", "recall", "k"): [3, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97,
                                    129, 193, 257, 385, 513],
        ("strand", "recall", "age"): list(range(8)),
        ("nest", "read", "depth"): list(range(1, 6)),
    }
    for n in (4, 5, 6):
        fams[("situation", "overlap_sim", f"m|n={n}")] = list(range(1, n))

    def q_of(fam, x):
        s, r, key = fam
        if key.startswith("m|"):
            return (s, r, {"n": key.split("=")[1], "m": str(x)})
        return (s, r, {key: str(x)})

    t0 = time.time()
    truth = {(fam, x): world.truth(q_of(fam, x), seeds=range(1000, 1005))
             for fam, grid in fams.items() for x in grid}
    rng = random.Random(rng_seed)
    rows = []   # (rule, depth, conf, correct, fam)
    abstain = 0
    total_unmeasured = 0
    for t in range(trials if not QUICK else 10):
        for fam, grid in fams.items():
            frac = rng.choice((0.3, 0.5, 0.7))
            measured = [x for x in grid if rng.random() < frac]
            pts = {x: world.measure(q_of(fam, x), rng.randrange(10**6))
                   for x in measured}
            concl = rz.ordinal_infer(pts, grid)
            total_unmeasured += len(grid) - len(measured)
            abstain += len(grid) - len(measured) - len(concl)
            for c in concl:
                rows.append((c.rule, c.depth, c.conf,
                             c.value == truth[(fam, c.param)], fam[0]))
    print(f" rng seed {rng_seed}: {len(rows)} conclusions over {total_unmeasured} unmeasured points "
          f"(abstained on {abstain}: {abstain/total_unmeasured:.2f}); "
          f"truth scoring only ({time.time()-t0:.0f}s)")
    out = {}
    for rule in ("sandwich", "extrapolate"):
        b = [r for r in rows if r[0] == rule]
        if not b:
            continue
        acc = np.mean([r[3] for r in b])
        out[rule] = (len(b), acc)
        print(f"  {rule:12s} N={len(b):4d} acc={acc:.3f} mean_conf={np.mean([r[2] for r in b]):.3f}")
    print("  extrapolation accuracy by chain depth (grid steps beyond last known):")
    for d in range(1, 9):
        b = [r for r in rows if r[0] == "extrapolate" and r[1] == d]
        if len(b) >= 5:
            out[("extrapolate", d)] = (len(b), np.mean([r[3] for r in b]))
            print(f"    depth {d}: N={len(b):4d} acc={np.mean([r[3] for r in b]):.3f} "
                  f"conf={np.mean([r[2] for r in b]):.3f}")
    print("  by family:")
    for f in sorted({r[4] for r in rows}):
        b = [r for r in rows if r[4] == f]
        print(f"    {f:10s} N={len(b):4d} acc={np.mean([r[3] for r in b]):.3f}")
    return out


if __name__ == "__main__":
    t0 = time.time()
    res = {}
    res["e1"] = e1_calibration(800 if QUICK else 3000)
    res["e2"] = e2_analogy()
    res["e3"] = e3_chain()
    res["e4"] = e4_closure()
    res["e5"] = e5_abstraction()
    res["e6"] = e6_nesting()
    res["e7"] = e7_ordinal()
    banner("E7b held-out draw (rng seed 8) after refitting the extrapolation decay on seed 7")
    res["e7b"] = e7_ordinal(rng_seed=8)
    print(f"\n(total {time.time()-t0:.0f}s)")
