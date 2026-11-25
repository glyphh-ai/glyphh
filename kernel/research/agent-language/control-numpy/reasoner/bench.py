"""Measurements for shared/reason.py. Every function returns a dict of numbers.

    python3 reasoner/bench.py            # full run, prints a table
Tests (reasoner/test_reason.py) call the same functions at smaller sizes.
All benchmarks use a private Lexicon(path=None) so no throwaway word lands
in shared/vocab.txt.
"""
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

import language as L  # noqa: E402
import reason as R  # noqa: E402


def private():
    return R.Reasoner(lex=L.Lexicon(path=None, load=False))


# ---------------------------------------------------------------- A. slot query + calibration
def bench_query(n=1500, seed=1, tau=0.8):
    """Held-out synthetic slot queries (seed differs from the calibration fit)."""
    cal = R.Calibrator.load() or R.fit_calibration(save=False)
    q = R.synthetic_queries(n, np.random.default_rng(seed))
    p = np.array([cal.p(z, g) for g, _, _, z in q])
    c = np.array([ok for _, ok, _, _ in q])
    ans = p >= tau
    return {"n": n, "ece": R.ece(p, c),
            "coverage": float(ans.mean()),
            "acc_answered": float(c[ans].mean()) if ans.any() else float("nan"),
            "acc_forced": float(c.mean()),
            "acc_abstained_would_be": float(c[~ans].mean()) if (~ans).any() else float("nan")}


# ---------------------------------------------------------------- B. record analogy
def bench_analogy(worlds=40, seed=2):
    """'What is the dollar of Mexico?' Two records with the same roles and
    different fillers; ask for the counterpart of a filler of A in B."""
    rng = np.random.default_rng(seed)
    Rz = private()
    roles = ["name", "loc", "val", "topic", "agent", "time", "src", "attr"]
    pool = [f"x{i}" for i in range(400)]
    Rz.lex.learn(pool, persist=False)
    book = R.Codebook(pool)
    two = mapping = idk = 0
    total = 0
    for _ in range(worlds):
        k = int(rng.integers(3, len(roles) + 1))
        rs = list(rng.choice(roles, k, replace=False))
        fa = list(rng.choice(pool, k, replace=False))
        fb = list(rng.choice([w for w in pool if w not in fa], k, replace=False))
        A = Rz.encode(dict(zip(rs, fa)))
        B = Rz.encode(dict(zip(rs, fb)))
        for j in range(k):
            total += 1
            two += Rz.analogy(A, B, fa[j], book=book).value == fb[j]
            mapping += Rz.analogy_mapping(A, B, fa[j], book=book).value == fb[j]
        # a filler that is NOT in A: the right answer is unknown
        stranger = str(rng.choice([w for w in pool if w not in fa and w not in fb]))
        idk += not Rz.analogy(A, B, stranger, book=book).known
    return {"queries": total, "two_step_acc": two / total, "mapping_acc": mapping / total,
            "abstain_on_absent": idk / worlds}


# ---------------------------------------------------------------- C. fact analogy
def bench_fact_analogy(n_pairs=30, seed=3):
    """A:B :: C:? over a fact memory with several relations."""
    rng = np.random.default_rng(seed)
    Rz = private()
    fm = R.FactMemory(Rz)
    rels = ["capital_of", "currency_of", "spoken_in", "made_by"]
    triples = {}
    for rel in rels:
        for i in range(n_pairs):
            triples[(f"{rel}_s{i}", rel)] = f"{rel}_o{i}"
            fm.add(f"{rel}_s{i}", rel, f"{rel}_o{i}")
    keys = list(triples)
    ok = n = 0
    for _ in range(200):
        (a, rel), (c, rel2) = [keys[i] for i in rng.choice(len(keys), 2, replace=False)]
        if rel != rel2:
            continue
        n += 1
        ok += Rz.analogy_facts(fm, a, triples[(a, rel)], c).value == triples[(c, rel)]
    # C has no fact of that relation -> unknown
    idk = sum(not Rz.analogy_facts(fm, "capital_of_s0", "capital_of_o0", f"nobody{i}").known
              for i in range(20))
    # A and B unrelated -> unknown
    idk2 = sum(not Rz.analogy_facts(fm, "capital_of_s0", "made_by_o1", "capital_of_s2").known
               for _ in range(1))
    return {"queries": n, "acc": ok / max(n, 1), "abstain_no_C_fact": idk / 20,
            "abstain_unrelated_AB": idk2}


# ---------------------------------------------------------------- D. abstraction
def bench_abstraction(trials=30, n_cases=15, n_roles=8, n_const=3, exception=0.2, seed=4):
    """n_cases records share n_const constant role fillers (each flipped to a
    random value with prob `exception`), other roles random. Recover the gist."""
    rng = np.random.default_rng(seed)
    Rz = private()
    roles = [f"g{i}" for i in range(n_roles)]
    Rz.lex.learn(roles=roles, persist=False)
    pool = [f"v{i}" for i in range(300)]
    Rz.lex.learn(pool, persist=False)
    book = R.Codebook(pool)
    tp = fp = fn = right_val = 0
    cls_ok = cls_n = 0
    for _ in range(trials):
        protos = {}
        for concept in ("c0", "c1"):
            const = dict(zip(rng.choice(roles, n_const, replace=False), rng.choice(pool, n_const)))
            cases = []
            for _ in range(n_cases + 5):
                m = {r: (const[r] if r in const and rng.random() > exception else str(rng.choice(pool)))
                     for r in roles}
                cases.append(Rz.encode(m))
            train, test = cases[:n_cases], cases[n_cases:]
            proto, gist, _ = Rz.abstract(train, roles=roles, book=book)
            protos[concept] = (proto, test)
            if concept == "c0":
                for r in roles:
                    got = r in gist
                    tp += got and r in const
                    fp += got and r not in const
                    fn += (not got) and r in const
                    right_val += got and r in const and gist[r].value == const[r]
        pmap = {c: p for c, (p, _) in protos.items()}
        for c, (_, test) in protos.items():
            for v in test:
                cls_n += 1
                cls_ok += Rz.classify(v, pmap).guess == c
    return {"gist_precision": tp / max(tp + fp, 1), "gist_recall": tp / max(tp + fn, 1),
            "gist_value_acc": right_val / max(tp, 1), "classify_acc": cls_ok / cls_n,
            "n_cases": n_cases, "exception_rate": exception}


# ---------------------------------------------------------------- E. chained inference
def taxonomy(depth=5, branch=3, props_every=2, rng=None):
    """A tree of is_a edges; some nodes carry a 'has' property inherited downward."""
    rng = rng or np.random.default_rng(0)
    edges, props = [], []
    frontier = ["n"]
    for d in range(depth):
        nxt = []
        for p in frontier:
            for b in range(branch):
                c = f"{p}{b}"
                edges.append((c, "is_a", p))
                nxt.append(c)
        frontier = nxt
    nodes = ["n"] + [c for c, _, _ in edges]
    for i, n in enumerate(nodes):
        if len(n) <= depth - 1 and rng.random() < 1 / props_every:
            props.append((n, "has", f"prop_{n}"))
    return edges, props


def closure(edges, props):
    """Symbolic ground truth for transitive is_a + inherit has."""
    parent = {c: p for c, _, p in edges}
    anc = {}
    for c in parent:
        a, x = [], c
        while x in parent:
            x = parent[x]
            a.append(x)
        anc[c] = a
    truth = set()
    for c, a in anc.items():
        truth |= {(c, "is_a", x) for x in a}
    has = {}
    for n, _, p in props:
        has.setdefault(n, []).append(p)
    for c, a in anc.items():
        for x in a:
            truth |= {(c, "has", p) for p in has.get(x, [])}
    return truth - set(edges) - set(props)


def bench_inference(depth=4, branch=3, seed=5):
    rng = np.random.default_rng(seed)
    Rz = private()
    fm = R.FactMemory(Rz)
    edges, props = taxonomy(depth, branch, rng=rng)
    for f in edges + props:
        fm.add(*f)
    truth = closure(edges, props)
    rules = [R.transitive("is_a"), R.inherit("has")]
    t0 = time.time()
    new = fm.infer(rules, max_depth=10, min_conf=0.0)
    dt = time.time() - t0
    got = {(f.s, f.r, f.o) for f in new}
    rechecks = [R.recheck((f.s, f.r, f.o), f.rule,
                          [(fm.facts[p].s, fm.facts[p].r, fm.facts[p].o) for p in f.premises])
                for f in new]
    # decode the proof tree of every conclusion from its vector alone
    exact = 0
    for f in new:
        node = Rz.explain(fm, fm.vec(f.fid), depth=1)
        want = [(fm.facts[p].s, fm.facts[p].r, fm.facts[p].o) for p in f.premises]
        exact += node["fact"] == (f.s, f.r, f.o) and \
            [k["fact"] for k in node.get("because", [])] == want
    # full-depth explanations: does the tree bottom out in told facts?
    deep = [f for f in new if f.depth >= 2][:30]
    leaves_ok = 0
    for f in deep:
        tree = Rz.explain(fm, fm.vec(f.fid), depth=10)
        leaves_ok += _tree_ok(tree, fm, set(edges) | set(props))
    return {"told": len(edges) + len(props), "derived": len(new), "truth": len(truth),
            "precision": len(got & truth) / max(len(got), 1),
            "recall": len(got & truth) / max(len(truth), 1),
            "recheck_pass": float(np.mean(rechecks)) if rechecks else 1.0,
            "explain_step_exact": exact / max(len(new), 1),
            "deep_trees_checked": len(deep),
            "deep_trees_ground_in_told": leaves_ok / max(len(deep), 1),
            "max_depth": max(f.depth for f in new), "seconds": round(dt, 2)}


def _tree_ok(node, fm, told):
    if "because" not in node:
        return node["fact"] in told
    kids = node["because"]
    if not kids:
        return False
    f = fm.facts.get(R.fact_id(*node["fact"]))
    if f is None or not R.recheck(node["fact"], node["rule"], [k["fact"] for k in kids]):
        return False
    return all(_tree_ok(k, fm, told) for k in kids)


# ---------------------------------------------------------------- F. calibrated inference
def bench_calibrated_inference(depth=4, branch=3, false_rate=0.25, seed=6, tau=0.8):
    """Told facts come with trust (as memory's KB would grade them): true ones
    mostly high, some false ones injected with lower trust. Derived conf =
    product of premise trust -> is it calibrated against the real world?"""
    rng = np.random.default_rng(seed)
    Rz = private()
    fm = R.FactMemory(Rz)
    edges, props = taxonomy(depth, branch, rng=rng)
    world = set(edges) | set(props) | closure(edges, props)
    nodes = sorted({e[0] for e in edges} | {"n"})
    told = []
    for f in edges + props:
        told.append((f, True))
    for _ in range(int(false_rate * len(edges))):   # false is_a edges, e.g. a noisy teller
        a, b = rng.choice(nodes, 2, replace=False)
        f = (str(a), "is_a", str(b))
        if f not in world:
            told.append((f, False))
    for f, ok in told:
        # trust as a Beta posterior after a few outside grades; graders are right 85%
        n_gr = int(rng.integers(1, 5))
        oks = int((rng.random(n_gr) < (0.85 if ok else 0.15)).sum())
        fm.add(*f, conf=(1 + oks) / (2 + n_gr))
    new = fm.infer([R.transitive("is_a", 1.0), R.inherit("has", reliability=1.0)], max_depth=6,
                   decay=1.0, min_conf=0.05)
    conf = np.array([f.conf for f in new])
    corr = np.array([(f.s, f.r, f.o) in world for f in new])
    told_conf = np.array([fm.facts[R.fact_id(*f)].conf for f, _ in told])
    told_corr = np.array([ok for _, ok in told])
    # grading feedback: half the conclusions get graded against the world,
    # the reasoner learns raw-conf -> P(right); measured on the other half
    idx = rng.permutation(len(new))
    tr, te = idx[: len(idx) // 2], idx[len(idx) // 2:]
    fm.learn_from_grades([(new[i].fid, bool(corr[i])) for i in tr])
    cal = np.array([fm.conf(new[i]) for i in te])
    ans = cal >= tau
    return {"told": len(told), "derived": len(new), "derived_true_frac": float(corr.mean()),
            "ece_told_trust": R.ece(told_conf, told_corr),
            "ece_derived_raw": R.ece(conf[te], corr[te]),
            "ece_derived_after_grades": R.ece(cal, corr[te]),
            "coverage_at_tau": float(ans.mean()),
            "acc_answered_at_tau": float(corr[te][ans].mean()) if ans.any() else float("nan"),
            "acc_abstained": float(corr[te][~ans].mean()) if (~ans).any() else float("nan")}


# ---------------------------------------------------------------- G. growing QA
def bench_growing_qa(depth=4, branch=3, seed=7):
    """Questions (s has ?) / (s is_a ?) answered before and after inference,
    plus questions about things nobody told us (must be 'unknown')."""
    rng = np.random.default_rng(seed)
    Rz = private()
    fm = R.FactMemory(Rz)
    edges, props = taxonomy(depth, branch, rng=rng)
    for f in edges + props:
        fm.add(*f)
    truth = closure(edges, props) | set(edges) | set(props)
    leaves = [c for c, _, _ in edges if len(c) == depth + 1]
    has_answer = [c for c in leaves if any(t[0] == c and t[1] == "has" for t in truth)]
    no_answer = [c for c in leaves if c not in has_answer]
    qs = [(str(c), "has") for c in rng.choice(has_answer, min(40, len(has_answer)), replace=False)]
    unknown = [(f"ghost{i}", "has") for i in range(20)] + [("n", "is_a")] + \
        [(str(c), "has") for c in no_answer[:20]]

    def score():
        ok = ans = 0
        for s, r in qs:
            a = fm.ask(s, r)
            ans += a.known
            ok += a.known and (s, r, a.value) in truth
        idk = sum(not fm.ask(s, r).known for s, r in unknown)
        return ok / len(qs), ans / len(qs), idk / len(unknown)

    before = score()
    fm.infer([R.transitive("is_a"), R.inherit("has")])
    after = score()
    return {"answerable": len(qs), "unanswerable": len(unknown),
            "acc_before": before[0], "coverage_before": before[1],
            "acc_after": after[0], "coverage_after": after[1],
            "abstain_unanswerable_before": before[2], "abstain_unanswerable_after": after[2]}


def main():
    for name, fn in [("A query+calibration", bench_query), ("B record analogy", bench_analogy),
                     ("C fact analogy", bench_fact_analogy), ("D abstraction", bench_abstraction),
                     ("E chained inference", bench_inference),
                     ("F calibrated inference", bench_calibrated_inference),
                     ("G growing QA", bench_growing_qa)]:
        t0 = time.time()
        res = fn()
        print(f"{name:26s} {time.time() - t0:6.1f}s  " +
              "  ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in res.items()),
              flush=True)


if __name__ == "__main__":
    main()
