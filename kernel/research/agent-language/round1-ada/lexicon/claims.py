"""Lexicon's claims about the language, each one a reproducible measurement.

    python3 agents/lexicon/claims.py measure <subject> <relation> [k=v ...] [--seed N]
    python3 agents/lexicon/claims.py tell       # file every claim in the KB (author=lexicon)

A grader reproduces a claim by running `measure` with ITS OWN seed: the
seed picks the vocabulary (Lexicon(seed=...)) and the random frames, so
agreement means the property belongs to the grammar, not to one draw.
Same shape as memory/world.py: measure(question, seed) -> answer word.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

_SHARED = Path(__file__).resolve().parents[1] / "shared"
sys.path.insert(0, str(_SHARED))
from language import Lexicon, bind, bundle, roll, sim  # noqa: E402
from glyphh_kernel import Space  # noqa: E402

Question = Tuple[str, str, Dict[str, str]]
DRAWS = 5


def _world(seed: int, n_words: int = 1000, n_roles: int = 80):
    lx = Lexicon(path=None, seed=seed)
    lx.typed = False     # the plain grammar; typed reading has its own claim
    words = [f"w{i}" for i in range(n_words)]
    roles = [f"r{i}" for i in range(n_roles)]
    for w in words:
        lx.word(w)
    for r in roles:
        lx.role(r)
    return lx, words, roles, random.Random(seed)


def blind_decode(slots: int, seed: int) -> str:
    """A random frame of `slots` word slots, decoded with no hint of which
    roles it has: exact over DRAWS frames?  exact | lossy"""
    lx, words, roles, rng = _world(seed)
    for _ in range(DRAWS):
        f = {r: rng.choice(words) for r in rng.sample(roles, slots)}
        if lx.decode(lx.encode(f), depth=0) != f:
            return "lossy"
    return "exact"


def _tree(rng, words, roles, m, d):
    f = {r: rng.choice(words) for r in rng.sample(roles, m)}
    if d > 1:
        f[rng.choice(list(f))] = _tree(rng, words, roles, m, d - 1)
    return f


def nest_decode(depth: int, slots: int, chunked: bool, seed: int) -> str:
    """A tree of `slots`-slot frames nested `depth` deep: exact decode over
    DRAWS trees?  With chunked=True every sub-frame is chunk()ed first.
    exact | lossy"""
    lx, words, roles, rng = _world(seed)
    for _ in range(DRAWS):
        t = _tree(rng, words, roles, slots, depth)
        g = lx.encode(t)
        if chunked:
            lx.chunk(t)
        if lx.decode(g, depth=depth + 1, expand=chunked) != t:
            return "lossy"
    return "exact"


def chunk_changes_glyph(seed: int) -> str:
    lx, words, roles, rng = _world(seed, 200, 20)
    t = _tree(rng, words, roles, 4, 4)
    g = lx.encode(t)
    return "yes" if not (lx.encode(lx.chunk(t)) == g).all() else "no"


def space_identical(seed: int) -> str:
    lx, words, roles, rng = _world(seed, 200, 20)
    for _ in range(DRAWS):
        f = {r: rng.choice(words) for r in rng.sample(roles, rng.randint(1, 8))}
        if not (lx.encode(f) == Space(seed=seed).encode(f)).all():
            return "no"
    return "yes"


def unrolled_nesting_confuses(seed: int) -> str:
    """Without the roll on composite fillers, is path A.B the same glyph
    as path B.A?  yes | no  (the reason the grammar rolls)"""
    lx, *_ = _world(seed, 10, 4)
    A, B, w = lx.role("A"), lx.role("B"), lx.word("w")
    raw = sim(bind(A, bind(B, w)), bind(B, bind(A, w)))
    rolled = sim(bind(A, roll(bind(B, w), 1)), bind(B, roll(bind(A, w), 1)))
    return "yes" if raw > 0.99 and abs(rolled) < 0.1 else "no"


def random_reads(seed: int) -> str:
    lx, *_ = _world(seed)
    r = np.random.RandomState(seed)
    for _ in range(DRAWS * 4):
        g = (r.randint(0, 2, lx.dim) * 2 - 1).astype(np.int8)
        if lx.parse(g):
            return "something"
    return "nothing"


def typed_beats_untyped(slots: int, seen: int, seed: int) -> str:
    """Learned slot types (selectional preferences): after reading `seen`
    8-slot frames whose roles each draw from a 20-word vocabulary, does
    typed reading recover MORE slots of fresh `slots`-slot frames (from
    another speaker) than untyped reading?  yes | no"""
    lx, words, roles, rng = _world(seed, 3000, 60)
    vocab = {r: rng.sample(words, 20) for r in roles}
    frame = lambda k: {r: rng.choice(vocab[r]) for r in rng.sample(roles, k)}
    for _ in range(seen):
        lx.encode(frame(8))
    speaker = Lexicon(path=None, seed=seed)
    tests = [frame(slots) for _ in range(DRAWS * 2)]
    glyphs = [speaker.encode(f) for f in tests]
    rec = {}
    for t in (False, True):
        lx.typed = t
        rec[t] = 0
        for f, g in zip(tests, glyphs):
            got = lx.decode(g, depth=0)
            got = got if isinstance(got, dict) else {}
            rec[t] += sum(got.get(r) == w for r, w in f.items())
    return "yes" if rec[True] > rec[False] else "no"


def measure(q: Question, seed: int) -> str:
    s, r, c = q
    if (s, r) == ("frame", "blind_decode"):
        return blind_decode(int(c["slots"]), seed)
    if (s, r) == ("nest_anonymous", "decode"):
        return nest_decode(int(c["depth"]), int(c["slots"]), False, seed)
    if (s, r) == ("nest_chunked", "decode"):
        return nest_decode(int(c["depth"]), int(c["slots"]), True, seed)
    if (s, r) == ("chunk", "changes_glyph"):
        return chunk_changes_glyph(seed)
    if (s, r) == ("flat_frame", "space_identical"):
        return space_identical(seed)
    if (s, r) == ("unrolled_nesting", "confuses_paths"):
        return unrolled_nesting_confuses(seed)
    if (s, r) == ("typed_reading", "beats_untyped"):
        return typed_beats_untyped(int(c["slots"]), int(c["seen"]), seed)
    if (s, r) == ("random_glyph", "reads_as"):
        return random_reads(seed)
    raise KeyError(q)


QUESTIONS = (
    [("frame", "blind_decode", {"slots": str(n)}) for n in (8, 16, 24, 48, 64)]
    + [("nest_anonymous", "decode", {"depth": str(d), "slots": "3"})
       for d in (1, 2, 4)]
    + [("nest_chunked", "decode", {"depth": "4", "slots": "6"}),
       ("chunk", "changes_glyph", {}),
       ("flat_frame", "space_identical", {}),
       ("unrolled_nesting", "confuses_paths", {}),
       ("random_glyph", "reads_as", {}),
       ("typed_reading", "beats_untyped", {"slots": "44", "seen": "300"}),
       ("typed_reading", "beats_untyped", {"slots": "16", "seen": "300"})])


def _how(q: Question) -> str:
    kv = " ".join(f"{k}={v}" for k, v in q[2].items())
    return (f"python3 agents/lexicon/claims.py measure {q[0]} {q[1]} {kv} "
            f"--seed <your seed>").replace("  ", " ")


def tell_all(seed: int = 4096) -> None:
    from knowledge import KB
    kb = KB()
    existing = {(c.subject, c.relation, tuple(sorted(c.context.items())))
                for c in kb.all_claims("lexicon")}
    for q in QUESTIONS:
        key = (q[0], q[1], tuple(sorted(q[2].items())))
        if key in existing:
            continue
        v = measure(q, seed)
        cid = kb.tell("lexicon", q[0], q[1], v, context=q[2] or None,
                      how=_how(q))
        print(cid, q, "->", v)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "tell":
        tell_all()
    elif args and args[0] == "measure":
        seed = 4096
        if "--seed" in args:
            i = args.index("--seed")
            seed = int(args[i + 1])
            args = args[:i] + args[i + 2:]
        ctx = dict(a.split("=", 1) for a in args[3:])
        print(measure((args[1], args[2], ctx), seed))
    else:
        print(__doc__)
