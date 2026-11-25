"""The world that grades knowledge in this experiment: the kernel itself.

Every question here is a MEASUREMENT of how the language behaves. Any
agent can answer it by running the measurement in its own world (its
own random draw: a private seed), and any other agent can check an
answer by running it again with ITS seed. Reproduced = win, not
reproduced = veto. Nobody grades their own answer.

    measure(question, seed, dim) -> answer string
    QUESTIONS -> list of (subject, relation, context) triples

`dim` and `decay` are world parameters: the drift test changes them
mid-stream (the group moves to dim 2048 and Strand decay 0.5), which
changes the true answer of several capacity questions -- exactly what
a veto must catch.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "kernel_v1"))
from glyphh_kernel import Strand, bind, bundle, roll, sim, symbol  # noqa: E402

READABLE = 0.08          # lexicon's decode threshold (~5 sigma at dim 4096)
Question = Tuple[str, str, Dict[str, str]]


def _syms(tag: str, n: int, seed: int, dim: int) -> List[np.ndarray]:
    """n random words for one draw. Same distribution as kernel
    symbol() (iid +/-1), generated in one batch for speed."""
    import hashlib
    h = hashlib.sha256(f"{seed}:{tag}".encode()).digest()
    rng = np.random.RandomState(np.frombuffer(h[:4], dtype=np.uint32))
    m = (rng.randint(0, 2, (n, dim), dtype=np.int8) * 2 - 1)
    return list(m)


def bundle_recall(k: int, seed: int, dim: int) -> str:
    """Bundle k random words; what fraction of members still read above
    threshold?  all | most | few"""
    parts = _syms("m", k, seed, dim)
    b = bundle(parts)
    frac = np.mean([sim(b, p) >= READABLE for p in parts])
    return "all" if frac == 1.0 else ("most" if frac >= 0.5 else "few")


def overlap_sim(n: int, m: int, seed: int, dim: int) -> str:
    """Two n-attribute situations sharing m attribute pairs: sim floored
    to one decimal."""
    roles = _syms("r", n, seed, dim)
    va, vb = _syms("a", n, seed, dim), _syms("b", n, seed, dim)
    a = bundle([bind(r, v) for r, v in zip(roles, va)])
    b = bundle([bind(r, (va[i] if i < m else vb[i]))
                for i, r in enumerate(roles)])
    return f"{np.round(sim(a, b), 1):.1f}"


def nest_read(depth: int, seed: int, dim: int) -> str:
    """A word nested `depth` frames deep (each frame has 3 slots, the
    word's path is role_0 at every level): does unbinding the path read
    it back above threshold?  readable | lost"""
    word = _syms("w:target", 1, seed, dim)[0]
    g = word
    for d in range(depth):
        rs = _syms(f"L{d}", 3, seed, dim)
        fill = _syms(f"F{d}", 2, seed, dim)
        g = bundle([bind(rs[0], g), bind(rs[1], fill[0]), bind(rs[2], fill[1])])
    probe = g
    for d in reversed(range(depth)):
        probe = bind(probe, _syms(f"L{d}", 3, seed, dim)[0])
    return "readable" if sim(probe, word) >= READABLE else "lost"


def strand_recall(age: int, seed: int, dim: int, length: int = 8,
                  decay: float = 0.7) -> str:
    """In a Strand of `length` codons (decay = world decay), can the codon `age`
    steps back be read out of state() (roll back by age)?  yes | no"""
    cod = _syms("c", length, seed, dim)
    st = Strand(list(cod)).state(decay)
    target = cod[length - 1 - age]
    return "yes" if sim(roll(st, -age), target) >= READABLE else "no"


FAMILIES = {
    ("bundle", "recall"): (bundle_recall, "k"),
    ("strand", "recall"): (strand_recall, "age"),
    ("nest", "read"): (nest_read, "depth"),
}


def questions() -> List[Question]:
    qs: List[Question] = []
    for k in (3, 5, 9, 17, 33, 65, 129, 257, 513):
        qs.append(("bundle", "recall", {"k": str(k)}))
    for age in range(8):
        qs.append(("strand", "recall", {"age": str(age)}))
    for depth in range(1, 6):
        qs.append(("nest", "read", {"depth": str(depth)}))
    for n in (2, 3, 4, 5, 6):
        for m in range(1, n):
            qs.append(("situation", "overlap_sim", {"n": str(n), "m": str(m)}))
    return qs


DRAWS = 5   # one measurement = majority over DRAWS independent sub-draws


def measure(q: Question, seed: int, dim: int = 4096,
            decay: float = 0.7) -> str:
    """One agent's measurement: the majority answer over DRAWS random
    draws derived from its private seed (a better instrument than a
    single draw, still not noise-free at small dim)."""
    votes: Dict[str, int] = {}
    for j in range(DRAWS):
        a = _measure_once(q, seed * DRAWS + j, dim, decay)
        votes[a] = votes.get(a, 0) + 1
    return max(sorted(votes), key=votes.get)


def _measure_once(q: Question, seed: int, dim: int, decay: float) -> str:
    subject, relation, ctx = q
    if (subject, relation) == ("situation", "overlap_sim"):
        return overlap_sim(int(ctx["n"]), int(ctx["m"]), seed, dim)
    if (subject, relation) == ("strand", "recall"):
        return strand_recall(int(ctx["age"]), seed, dim, decay=decay)
    fn, key = FAMILIES[(subject, relation)]
    return fn(int(ctx[key]), seed, dim)


def truth(q: Question, dim: int = 4096, decay: float = 0.7,
          seeds=range(1000, 1009)) -> str:
    """Ground truth for scoring only (never seen by the agents): the
    majority answer over 9 held-out seeds."""
    votes: Dict[str, int] = {}
    for s in seeds:
        a = measure(q, s, dim, decay)
        votes[a] = votes.get(a, 0) + 1
    return max(votes, key=votes.get)
