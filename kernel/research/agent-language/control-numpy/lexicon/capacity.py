"""Capacity measurements for shared/language.py (owner: lexicon).

Run:  python3 lexicon/capacity.py [--quick]
Every number is exact-match of the WHOLE decoded meaning against the original
(no partial credit) unless labelled 'slot acc'. Throwaway lexicons (path=None):
nothing is written to shared/vocab.txt.
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "shared"))
import language as L  # noqa: E402

QUICK = "--quick" in sys.argv
TRIALS = 20 if QUICK else 60


def make_lex(dim, n_words, n_roles):
    lex = L.Lexicon(dim=dim, path=None, load=False)
    lex.learn([f"w{i}" for i in range(n_words)], [f"r{i}" for i in range(n_roles)], persist=False)
    return lex


def rand_flat(rng, k, n_words, n_roles):
    roles = rng.choice(n_roles, k, replace=False)
    return {f"r{r}": f"w{rng.integers(n_words)}" for r in roles}


def rand_tree(rng, depth, branch, n_words, n_roles):
    """Frame with `branch` slots; one slot holds a sub-tree until `depth` is used up."""
    m = rand_flat(rng, branch, n_words, n_roles)
    if depth > 1:
        m[next(iter(m))] = rand_tree(rng, depth - 1, branch, n_words, n_roles)
    return m


def leaves(m):
    if isinstance(m, str):
        return 1
    vals = m.values() if isinstance(m, dict) else m
    return 1 + sum(leaves(v) for v in vals)          # +1 = the FRAME marker


# the rejected v0 grammar: sign at every level (kept here only for comparison)
def enc_sign_each_level(m, dim):
    if isinstance(m, str):
        return L.atom(m, dim)
    parts = [L.atom(L.FRAME, dim)] + [L.bind(L.role(r, dim), L.permute(enc_sign_each_level(f, dim), 1))
                                       for r, f in m.items()]
    return L.bundle(parts, dim)


def exact(lex, m, v, peel=4):
    return L.decode(v, lex, peel=peel) == m


def run():
    warnings.simplefilter("ignore")  # over-budget meanings are measured on purpose
    rng = np.random.default_rng(0)
    res = {}
    t0 = time.time()

    # 1. flat frames: how many role-filler pairs fit in one vector?
    print("\n[1] flat frame, N=1000 words, 256 roles: exact-match rate vs k (pairs) and D")
    print("    plain = one-pass reader (peel=0); peel = explaining-away reader (peel=4, the default)")
    ks = [4, 8, 16, 24, 32, 48, 64, 96, 128, 160, 192, 256]
    dims = [1024, 2048, 4096, 8192]
    res["flat"] = {}
    print("   D    reader " + "".join(f"{k:>6}" for k in ks))
    for dim in dims:
        lex = make_lex(dim, 1000, 256)
        rows = {0: [], 4: []}
        for k in ks:
            ms = [rand_flat(rng, k, 1000, 256) for _ in range(TRIALS // 2)]
            vs = [L.encode(m, lex, persist=False) for m in ms]
            for pl in rows:
                if k > dim // 16:          # far past any reader's limit: skip the cost
                    rows[pl].append(0.0); continue
                rows[pl].append(sum(exact(lex, m, v, pl) for m, v in zip(ms, vs)) / len(ms))
        res["flat"][dim] = {"plain": dict(zip(ks, rows[0])), "peel": dict(zip(ks, rows[4]))}
        for pl, name in ((0, "plain"), (4, "peel ")):
            print(f"  {dim:>6} {name} " + "".join(f"{x:6.2f}" for x in rows[pl]))

    # 2. nesting: depth x branching, flat-sum grammar (v1) vs sign-each-level (v0)
    print("\n[2] nesting, D=8192, N=1000, 64 roles: exact-match, v1 (sign once) vs v0 (sign each level)")
    lex = make_lex(8192, 1000, 64)
    res["depth"] = {}
    for branch in (2, 3, 4):
        for depth in (1, 2, 3, 4, 5, 6):
            ms = [rand_tree(rng, depth, branch, 1000, 64) for _ in range(TRIALS)]
            v1 = sum(exact(lex, m, L.encode(m, lex, persist=False)) for m in ms) / TRIALS
            v0 = sum(exact(lex, m, enc_sign_each_level(m, 8192), 0) for m in ms) / TRIALS
            res["depth"][f"b{branch}d{depth}"] = {"v1": v1, "v0": v0, "leaves": leaves(ms[0])}
            print(f"   branch={branch} depth={depth} leaves={leaves(ms[0]):>3}:  v1={v1:.2f}  v0={v0:.2f}")

    # 3. vocabulary size: does a bigger lexicon hurt?
    print("\n[3] vocabulary size, D=8192, flat k=16 and k=32")
    res["vocab"] = {}
    for n in (100, 1000, 5000, 20000):
        lex = make_lex(8192, n, 64)
        row = {}
        for k in (16, 32):
            row[k] = sum(exact(lex, m, L.encode(m, lex, persist=False))
                         for m in (rand_flat(rng, k, n, 64) for _ in range(TRIALS // 2))) / (TRIALS // 2)
        res["vocab"][n] = row
        print(f"   N={n:>6}: k16={row[16]:.2f}  k32={row[32]:.2f}")

    # 4. channel noise: flip a fraction of bits of the wire form
    print("\n[4] bit-flip noise on the wire, D=8192, N=1000, message = 8 slots with 1 nested frame of 4")
    lex = make_lex(8192, 1000, 64)
    res["noise"] = {}
    for p in (0.0, 0.05, 0.1, 0.2, 0.3, 0.4):
        ok = 0
        for _ in range(TRIALS):
            m = rand_flat(rng, 8, 1000, 64)
            m[next(iter(m))] = rand_flat(rng, 4, 1000, 64)
            w = L.to_wire(L.encode(m, lex, persist=False))
            bits = np.unpackbits(w)
            flip = rng.random(bits.size) < p
            bits[flip] ^= 1
            ok += exact(lex, m, np.packbits(bits))
        res["noise"][p] = ok / TRIALS
        print(f"   flip={p:.2f}: exact={ok / TRIALS:.2f}")

    # 5. false positives: random payloads must read as 'noise'; real ones must not
    print("\n[5] false positives, D=8192, real shared-style lexicon")
    lex = make_lex(8192, 1000, 64)
    n = 200
    fp_noise = sum(L.read_back(rng.integers(0, 256, 1024, dtype=np.uint8), lex).kind != "noise"
                   for _ in range(n))
    spurious = 0; total_slots = 0
    for _ in range(n // 4):
        m = rand_flat(rng, 12, 1000, 64)
        d = L.decode(L.encode(m, lex, persist=False), lex) or {}
        spurious += len(set(d) - set(m)); total_slots += len(lex.roles) - len(m)
    res["false_pos"] = {"random_payload_read_as_meaning": fp_noise / n,
                        "spurious_slot_rate": spurious / total_slots}
    print(f"   random 1024-byte payloads decoded as a meaning: {fp_noise}/{n}")
    print(f"   spurious slots in k=12 frames: {spurious}/{total_slots} empty-role probes")

    # 6. similarity structure: meanings that share slots have similar vectors
    print("\n[6] graded similarity, D=8192: sim(encode(m), encode(m with j of 8 slots changed))")
    lex = make_lex(8192, 1000, 64)
    res["graded"] = {}
    for j in (0, 1, 2, 4, 6, 8):
        ss = []
        for _ in range(TRIALS):
            m = rand_flat(rng, 8, 1000, 64)
            m2 = dict(m)
            for r in list(m)[:j]:
                m2[r] = f"w{rng.integers(1000)}"
            ss.append(L.sim(L.encode(m, lex, persist=False), L.encode(m2, lex, persist=False)))
        res["graded"][j] = float(np.mean(ss))
        print(f"   changed {j}/8: sim={np.mean(ss):.3f}")

    # 8. nested proofs: an answer whose :because lists n premise frames (5 leaves each)
    print("\n[8] nested proofs, D=8192, shared-style roles: (answer :content fact :because [n facts] :rule r)")
    lex = L.Lexicon(path=None, load=False)
    lex.learn([f"e{i}" for i in range(40)] + ["is_a", "transitive"], persist=False)
    res["proof"] = {}
    for n in (4, 8, 12, 16, 20, 24, 28, 31):
        ok0 = ok4 = 0
        T = max(TRIALS // 4, 5)
        for _ in range(T):
            ents = rng.permutation(40)[:n + 1]
            prem = [{"act": "fact", "subj": f"e{ents[i]}", "rel": "is_a", "obj": f"e{ents[i+1]}"} for i in range(n)]
            m = {"act": "answer", "content": {"act": "fact", "subj": f"e{ents[0]}", "rel": "is_a",
                                              "obj": f"e{ents[n]}"}, "because": prem, "rule": "transitive"}
            v = L.encode(m, lex, persist=False)
            ok0 += exact(lex, m, v, 0); ok4 += exact(lex, m, v, 4)
        res["proof"][n] = {"leaves": L.leaf_count(m), "plain": ok0 / T, "peel": ok4 / T}
        print(f"   premises={n:>2} leaves={L.leaf_count(m):>3}: plain={ok0 / T:.2f}  peel={ok4 / T:.2f}")

    # 7. speed
    lex = make_lex(8192, 1000, 64)
    m = rand_tree(rng, 3, 4, 1000, 64)
    t = time.time(); [L.encode(m, lex, persist=False) for _ in range(50)]; te = (time.time() - t) / 50
    v = L.encode(m, lex, persist=False)
    t = time.time(); [L.decode(v, lex) for _ in range(20)]; td = (time.time() - t) / 20
    t = time.time(); [L.decode(v, lex, peel=0) for _ in range(20)]; td0 = (time.time() - t) / 20
    res["speed_ms"] = {"encode": te * 1000, "decode_peel": td * 1000, "decode_plain": td0 * 1000}
    print(f"\n[7] speed (depth 3, branch 4, N=1000, 64+32 roles): encode {te*1000:.1f} ms, "
          f"decode {td*1000:.1f} ms (plain one-pass {td0*1000:.1f} ms)")
    print(f"\ntotal {time.time() - t0:.0f}s")
    out = HERE / ("capacity_quick.json" if QUICK else "capacity.json")
    out.write_text(json.dumps(res, indent=1, default=str))
    print("wrote", out)
    return res


if __name__ == "__main__":
    run()
