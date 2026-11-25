"""Capacity measurements for shared/language.py. Prints real numbers.

    python3 agents/lexicon/capacity.py [trials]

Every experiment uses a private in-memory Lexicon (path=None) so the
shared codebook is not polluted. Vocabulary: 1000 random words, 80 roles
registered up front (a realistic shared codebook size).
"""

import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from language import Lexicon, sim  # noqa: E402

N_WORDS, N_ROLES = 1000, 80


def fresh(threshold=None):
    # typed=False: [1]-[7] measure the plain grammar. The reader here is
    # also the speaker, so learned slot types would see the test frames;
    # [8] measures typed reading honestly (separate speaker).
    lx = Lexicon(path=None, threshold=threshold)
    lx.typed = False
    words = [f"w{i}" for i in range(N_WORDS)]
    roles = [f"r{i}" for i in range(N_ROLES)]
    for w in words:
        lx.word(w)
    for r in roles:
        lx.role(r)
    return lx, words, roles


def rand_frame(rng, words, roles, n):
    return {r: rng.choice(words) for r in rng.sample(roles, n)}


def flat_capacity(trials):
    """Exact-frame and per-slot accuracy vs slots per frame."""
    lx, words, roles = fresh()
    rng = random.Random(1)
    print("\n[1] FLAT FRAME: n slots bundled, decode (1000 words, "
          f"{len(lx.roles)} roles in codebook), {trials} trials")
    print(" n | exact | slot recall | false slots/frame | mean true sim")
    rows = []
    for n in [1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 24, 32, 40, 48, 64]:
        exact = hits = fp = 0
        sims = []
        for _ in range(trials):
            f = rand_frame(rng, words, roles, min(n, len(roles)))
            g = lx.encode(f)
            slots = lx.parse(g, depth=0)
            got = {p[0]: w for p, w, _ in slots}
            sims += [s for p, w, s in slots if f.get(p[0]) == w]
            h = sum(got.get(r) == w for r, w in f.items())
            hits += h
            fp += sum(1 for r in got if r not in f)
            exact += (got == f)
        rows.append((n, exact / trials, hits / (trials * n), fp / trials,
                     np.mean(sims) if sims else 0))
        print(f"{n:2d} | {exact/trials:5.2f} | {hits/(trials*n):11.3f} | "
              f"{fp/trials:17.2f} | {np.mean(sims) if sims else 0:.3f}")
    return rows


def probe_capacity(trials):
    """Known-role probing (the receiver knows which slot it wants):
    top-1 accuracy of probe(g, role) vs n. No threshold involved."""
    lx, words, roles = fresh()
    rng = random.Random(2)
    print("\n[2] PROBE ONE KNOWN SLOT: top-1 accuracy vs n (no threshold)")
    print(" n | top-1 acc")
    for n in [8, 16, 24, 32, 48, 64, 80]:
        ok = 0
        for _ in range(trials):
            f = rand_frame(rng, words, roles, n)
            g = lx.encode(f)
            r = rng.choice(list(f))
            ok += lx.probe(g, r, 1)[0][0] == f[r]
        print(f"{n:2d} | {ok/trials:.3f}")


def nested(trials):
    """A frame of `m` word slots nested `d` levels deep; each level also
    carries `m-1` sibling word slots. Anonymous vs chunked (define)."""
    rng = random.Random(3)
    print("\n[3] NESTING: frames of m slots, depth d, exact decode of the "
          "whole tree")
    print(" m | d | anonymous exact | chunked exact | innermost sim (anon)")
    for m in [3, 4, 6]:
        for d in [1, 2, 3, 4]:
            anon = chunk = 0
            inner_sims = []
            for t in range(trials):
                lx, words, roles = fresh()
                def build(level):
                    f = rand_frame(rng, words, roles, m)
                    if level < d:
                        k = rng.choice(list(f))
                        f[k] = build(level + 1)
                    return f
                tree = build(1)
                got = lx.decode(lx.encode(tree), depth=d + 1)
                anon += got == tree
                # innermost signal: walk the path, probe the leaf
                node, g = tree, lx.encode(tree)
                from language import bind, roll
                while True:
                    ks = [k for k, v in node.items() if isinstance(v, dict)]
                    if not ks:
                        leaf = next(iter(node))
                        inner_sims.append(sim(bind(g, lx.role(leaf)),
                                              lx.word(node[leaf])))
                        break
                    k = ks[0]
                    g = roll(bind(g, lx.role(k)), -1)
                    node = node[k]
                # chunked: define bottom-up, every nested frame a concept
                def chunked(f, name):
                    out = {}
                    for k, v in f.items():
                        out[k] = chunked(v, name + k) if isinstance(v, dict) else v
                    lx.define(name, out)
                    return name
                top = chunked(tree, f"c{t}_")
                top_meaning = lx.concepts[top]["meaning"]
                got2 = lx.decode(lx.encode(top_meaning), depth=0)
                def expand(x):
                    if isinstance(x, str) and x in lx.concepts:
                        return expand(lx.concepts[x]["meaning"])
                    if isinstance(x, dict):
                        return {k: expand(v) for k, v in x.items()}
                    return x
                chunk += expand(got2) == tree
            print(f"{m:2d} | {d} | {anon/trials:15.2f} | {chunk/trials:13.2f} |"
                  f" {np.mean(inner_sims):.3f}")


def sequences(trials):
    lx, words, roles = fresh()
    rng = random.Random(4)
    print("\n[4] LISTS (positional roles #1..#16): exact decode vs length")
    print(" len | exact | item recall")
    for L in [2, 4, 8, 12, 16]:
        ex = it = 0
        for _ in range(trials):
            xs = [rng.choice(words) for _ in range(L)]
            got = lx.decode(lx.encode(xs), depth=0)
            ex += got == xs
            if isinstance(got, list):
                it += sum(a == b for a, b in zip(got, xs))
        print(f"{L:4d} | {ex/trials:5.2f} | {it/(trials*L):.3f}")


def noise_floor(trials):
    """Random glyphs (no meaning) must decode to nothing. Also: the
    max noise sim over the whole (roles x fillers) table."""
    lx, words, roles = fresh()
    rng = np.random.RandomState(5)
    print(f"\n[5] NOISE: random glyphs through parse (adaptive thr "
          f"{lx.thr():.4f})")
    fps, maxes = 0, []
    for _ in range(trials):
        g = (rng.randint(0, 2, lx.dim) * 2 - 1).astype(np.int8)
        fps += len(lx.parse(g, depth=1))
        maxes.append(lx._slot_scores(g).max())
    print(f" false slots per random glyph (depth 1): {fps/trials:.3f}")
    print(f" max noise sim over {len(lx.roles)}x{len(lx.fillers)} table: "
          f"mean {np.mean(maxes):.4f}, worst {np.max(maxes):.4f} "
          f"(sigma = {1/np.sqrt(lx.dim):.4f})")
    # false slots on REAL frames (the case that matters), at scale
    rr = random.Random(8)
    fp = 0
    n_frames = trials * 10
    for _ in range(n_frames):
        f = rand_frame(rr, words, roles, 6)
        fp += sum(1 for p, w, s in lx.parse(lx.encode(f), depth=0)
                  if p[0] not in f)
    print(f" false slots on {n_frames} real 6-slot frames: {fp} "
          f"({fp/n_frames:.4f} per frame)")


def overlap(trials):
    lx, words, roles = fresh()
    rng = random.Random(6)
    print("\n[6] SIMILARITY = shared structure: two 6-slot frames sharing k "
          "slots")
    print(" k | sim")
    for k in range(7):
        ss = []
        for _ in range(trials):
            a = rand_frame(rng, words, roles, 6)
            b = dict(a)
            for r in rng.sample(list(a), 6 - k):
                b[r] = rng.choice(words)
            ss.append(lx.similar(a, b))
        print(f" {k} | {np.mean(ss):.3f}")


def typed(trials):
    """Selectional preferences learned from use. 3000-word codebook, 80
    roles, each role has its own 25-word vocabulary. The lexicon first
    reads `seen` training frames (learning which fillers each role
    takes), then blind-decodes fresh frames. typed=False is the plain
    global cleanup."""
    print("\n[8] LEARNED SLOT TYPES: exact blind decode vs training frames "
          "seen (3000 words, 80 roles x 25-word role vocabularies)")
    print(" slots | seen | untyped exact | typed exact | typed slot recall")
    for n in (32, 40, 48, 56):
        for seen in (0, 50, 400):
            rng = random.Random(9)
            lx = Lexicon(path=None)
            words = [f"w{i}" for i in range(3000)]
            for w in words:
                lx.word(w)
            roles = [f"r{i}" for i in range(80)]
            for r in roles:
                lx.role(r)          # roles known (shared codebook)
            vocab = {r: rng.sample(words, 25) for r in roles}
            def frame(k):
                return {r: rng.choice(vocab[r]) for r in rng.sample(roles, k)}
            for _ in range(seen):
                lx.encode(frame(8))
            test = [frame(n) for _ in range(trials)]
            # encoded by ANOTHER speaker (same vocabulary, same glyphs), so
            # the test frames do not teach the reader their types
            speaker = Lexicon(path=None)
            glyphs = [speaker.encode(f) for f in test]
            res = {}
            for t in (False, True):
                lx.typed = t
                ex = rec = 0
                for f, g in zip(test, glyphs):
                    got = lx.decode(g, depth=0)
                    got = got if isinstance(got, dict) else {}
                    ex += got == f
                    rec += sum(got.get(r) == w for r, w in f.items())
                res[t] = (ex / trials, rec / (trials * n))
            print(f" {n:5d} | {seen:4d} | {res[False][0]:13.2f} | "
                  f"{res[True][0]:11.2f} | {res[True][1]:.3f}")


def speed():
    lx, words, roles = fresh()
    msg = {"act": "tell", "from": "lexicon", "topic": "t",
           "content": {"subject": "a", "relation": "b", "object": "c"}}
    g = lx.encode(msg)
    t = time.time()
    for _ in range(10):
        lx.decode(g)
    print(f"\n[7] SPEED: decode of a nested message, {len(lx.roles)} roles x "
          f"{len(lx.fillers)} fillers: {(time.time()-t)/10*1000:.1f} ms")


if __name__ == "__main__":
    T = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    flat_capacity(T)
    probe_capacity(T * 4)
    nested(max(10, T // 2))
    sequences(T)
    noise_floor(T * 2)
    overlap(T)
    typed(T)
    speed()
