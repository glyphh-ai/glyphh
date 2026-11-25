"""reason.py -- thinking in the language (owner: reasoner).

Operations that PRODUCE new knowledge from existing glyphs instead of
just storing it. Every operation is kernel algebra (bind / bundle /
roll / sim) plus ONE decision rule, `judge`, that turns a noisy glyph
into either a named answer with a calibrated confidence or an honest
"I don't know".

    from reason import Frames, judge, analogy, chain, closure, abstract,
                       typical, classify, conclude, ask_glyph, answer_glyph

Vocabulary is lexicon's: role(r) = symbol("attr:"+r), word(w) =
symbol("val:"+w), seed 42, dim 4096. A subject's FRAME is the bundle of
bind(role(relation), word(object)) over its facts, in sorted order, so a
single-valued frame is bit-identical to LX.encode({...}) and to
Space.encode(situation).

The confidence rule (see judge()): with D-dim bipolar glyphs a random
candidate's sim is ~N(0, 1/D), sigma = 1/64 at D=4096. For the best of
V candidates we compute
    p_noise = 1 - Phi(top/sigma)^V          could noise alone reach top?
    p_sep   = Phi((top-second)/(sigma*sqrt2))  is top really above #2?
    conf    = (1 - p_noise) * p_sep
and say "known" only when conf >= KNOWN_AT. The numbers that justify
this are in reasoner/bench.py and reasoner/REPORT.md.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ADA = os.path.abspath(os.path.join(_HERE, "..", "..", "kernel_v1"))
if _ADA not in sys.path:
    sys.path.insert(0, _ADA)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from glyphh_kernel import DIM, bind, bundle, roll, sim, symbol  # noqa: E402

# Vocabulary: exactly lexicon's symbols (language.py: word = "val:",
# role = "attr:", seed 42). Built with the kernel directly so that
# reasoning over thousands of scratch words does not append them all to
# the shared codebook; publish() registers the words a result uses.
def W(w: str) -> np.ndarray:
    return symbol("val:" + w)


def R(r: str) -> np.ndarray:
    return symbol("attr:" + r)


def publish(words: Iterable[str] = (), roles: Iterable[str] = ()) -> None:
    """Register words/roles in lexicon's shared codebook so the others'
    LX.decode can read glyphs we built (we build with the kernel
    directly, so scratch vocabulary never floods the codebook)."""
    try:
        from language import LX
        for w in words:
            LX.word(w)
        for r in roles:
            LX.role(r)
    except Exception:
        pass


REASON_ROLES = ("claim", "because", "rule", "confidence")


SIGMA = 1.0 / math.sqrt(DIM)
KNOWN_AT = 0.90  # conf needed to say "known"; see bench calibration


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ── the decision rule ───────────────────────────────────────────────

class Candidates:
    """A cleanup memory: names and their glyphs, one matrix."""

    def __init__(self, names: Iterable[str], glyph_of=W):
        self.names = list(dict.fromkeys(names))
        self.index = {n: i for i, n in enumerate(self.names)}
        self.M = (np.stack([glyph_of(n) for n in self.names]).astype(np.float32)
                  if self.names else np.zeros((0, DIM), np.float32))

    @classmethod
    def of_glyphs(cls, named: Dict[str, np.ndarray]) -> "Candidates":
        c = cls([], W)
        c.names = list(named)
        c.index = {n: i for i, n in enumerate(c.names)}
        c.M = np.stack([named[n] for n in c.names]).astype(np.float32)
        return c

    def sims(self, g: np.ndarray) -> np.ndarray:
        return (self.M @ g.astype(np.float32)) / self.M.shape[1]

    def __len__(self) -> int:
        return len(self.names)


@dataclass
class Verdict:
    """What reasoning concluded about one noisy glyph."""
    answer: Optional[str]      # best candidate, None if known is False
    best: Optional[str]        # best candidate even when not trusted
    sim: float
    runner_up: Optional[str]
    runner_sim: float
    conf: float                # calibrated P(best is the answer)
    known: bool
    n: int                     # candidates considered

    def to_json(self) -> dict:
        return {"answer": self.answer, "best": self.best,
                "sim": round(self.sim, 4), "runner_up": self.runner_up,
                "runner_sim": round(self.runner_sim, 4),
                "conf": round(self.conf, 4), "known": self.known,
                "n": self.n}


def confidence(top: float, second: float, n: int,
               sigma: float = SIGMA) -> float:
    p_noise = 1.0 - _phi(top / sigma) ** max(n, 1)
    p_sep = _phi((top - second) / (sigma * math.sqrt(2.0)))
    return max(0.0, min(1.0, (1.0 - p_noise) * p_sep))


def judge(g: np.ndarray, cands: Candidates, exclude: Sequence[str] = (),
          known_at: float = KNOWN_AT) -> Verdict:
    """Clean up a noisy glyph against candidates, with a calibrated
    'I don't know'."""
    s = cands.sims(g)
    if exclude:
        s = s.copy()
        for e in exclude:
            if e in cands.index:
                s[cands.index[e]] = -np.inf
    n = int(np.isfinite(s).sum())
    if n == 0:
        return Verdict(None, None, 0.0, None, 0.0, 0.0, False, 0)
    order = np.argsort(s)[::-1]
    i1 = int(order[0])
    top = float(s[i1])
    if n > 1:
        i2 = int(order[1])
        second, runner = float(s[i2]), cands.names[i2]
    else:
        second, runner = 0.0, None
    c = confidence(top, max(second, 0.0) if n == 1 else second, n)
    known = c >= known_at
    best = cands.names[i1]
    return Verdict(best if known else None, best, top, runner, second,
                   c, known, n)


# ── a knowledge base as frames ──────────────────────────────────────

class Frames:
    """Facts (subject, relation, object) seen as one frame glyph per
    subject. The frame is the language's sentence for 'everything we
    know about s'."""

    def __init__(self, facts: Iterable[Tuple[str, str, str]] = ()):
        self.facts: set = set()
        self._frames: Dict[str, np.ndarray] = {}
        self._ents: Optional[Candidates] = None
        self._rels: Optional[Candidates] = None
        for f in facts:
            self.add(*f)

    def add(self, s: str, r: str, o: str) -> None:
        if (s, r, o) in self.facts:
            return
        self.facts.add((s, r, o))
        self._frames.pop(s, None)
        self._ents = self._rels = None

    # vocab
    @property
    def entities(self) -> Candidates:
        if self._ents is None:
            names = sorted({f[0] for f in self.facts} | {f[2] for f in self.facts})
            self._ents = Candidates(names, W)
        return self._ents

    @property
    def relations(self) -> Candidates:
        if self._rels is None:
            self._rels = Candidates(sorted({f[1] for f in self.facts}), R)
        return self._rels

    def about(self, s: str) -> List[Tuple[str, str]]:
        return sorted((r, o) for (x, r, o) in self.facts if x == s)

    def frame(self, s: str) -> np.ndarray:
        if s not in self._frames:
            parts = [bind(R(r), W(o)) for r, o in self.about(s)]
            if not parts:
                # unknown subject: its frame is its own name, which
                # unbinds to noise -> 'I don't know' downstream
                self._frames[s] = W(s)
            else:
                self._frames[s] = bundle(parts)
        return self._frames[s]

    def truth(self, s: str, r: str) -> List[str]:
        return sorted(o for (x, y, o) in self.facts if x == s and y == r)

    # the basic question
    def ask(self, s: str, r: str, known_at: float = KNOWN_AT) -> Verdict:
        """(s, r, ?) answered by unbinding the role from s's frame."""
        return judge(bind(self.frame(s), R(r)), self.entities,
                     known_at=known_at)

    def relation_between(self, a: str, b: str,
                         known_at: float = KNOWN_AT) -> Verdict:
        """(a, ?, b): unbind the FILLER, clean up against roles."""
        return judge(bind(self.frame(a), W(b)), self.relations,
                     known_at=known_at)


# ── analogy ─────────────────────────────────────────────────────────

def analogy(kb: Frames, a: str, b: str, c: str, mode: str = "relational",
            known_at: float = KNOWN_AT) -> Verdict:
    """a : b :: c : ?

    relational: find the role linking a to b (unbind b from a's frame,
      clean up to a role), then ask c for that role. Two cleanups.
    algebraic: Kanerva's 'dollar of Mexico' - one expression, one
      cleanup: bind(bind(frame(a), b), frame(c)).  The role is never
      named; it is carried as a noisy glyph.
    """
    if mode == "relational":
        rv = kb.relation_between(a, b, known_at=known_at)
        if not rv.known:
            return Verdict(None, None, rv.sim, None, 0.0, rv.conf, False, rv.n)
        v = kb.ask(c, rv.answer, known_at=known_at)
        conf = v.conf * rv.conf
        return Verdict(v.best if conf >= known_at else None, v.best, v.sim,
                       v.runner_up, v.runner_sim, conf, conf >= known_at, v.n)
    g = bind(bind(kb.frame(a), W(b)), kb.frame(c))
    return judge(g, kb.entities, exclude=(a, b, c), known_at=known_at)


# ── chained inference ───────────────────────────────────────────────

@dataclass
class Chain:
    path: List[str]            # entities visited, starting at s
    hops: List[Verdict]
    conf: float
    known: bool

    @property
    def answer(self) -> Optional[str]:
        return self.path[-1] if self.known else None


def chain(kb: Frames, s: str, rels: Sequence[str],
          known_at: float = KNOWN_AT) -> Chain:
    """Multi-hop with cleanup at every hop: s -r1-> x1 -r2-> x2 ...
    Confidence is the product of hop confidences; one unknown hop makes
    the whole chain unknown (we do not guess past a gap)."""
    path, hops, conf = [s], [], 1.0
    x = s
    for r in rels:
        v = kb.ask(x, r, known_at=0.0)  # follow the best, judge the product
        hops.append(v)
        conf *= v.conf
        x = v.best
        path.append(x)
    return Chain(path, hops, conf, conf >= known_at)


def graph_glyph(facts: Iterable[Tuple[str, str, str]]) -> np.ndarray:
    """The whole KB as ONE glyph: bundle of bind(bind(role r, s), roll(o))."""
    return bundle([bind(bind(R(r), W(s)), roll(W(o), 1))
                   for s, r, o in sorted(facts)])


def chain_holistic(G: np.ndarray, s: str, rels: Sequence[str],
                   ents: Candidates, known_at: float = KNOWN_AT) -> Verdict:
    """Multi-hop WITHOUT intermediate cleanup: the noisy hop result is
    the key for the next hop. Measures how far pure algebra carries."""
    x = W(s).astype(np.float32)
    for r in rels:
        y = bind_f(G, bind_f(R(r), x))
        x = np.roll(y, -1)
    return judge(np.sign(x + 1e-9).astype(np.int8), ents, known_at=known_at)


def bind_f(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """bind that keeps real values (for noisy intermediate glyphs)."""
    return a.astype(np.float32) * b.astype(np.float32)


@dataclass
class Derived:
    fact: Tuple[str, str, str]
    conf: float
    depth: int
    premises: List[Tuple[str, str, str]] = field(default_factory=list)


def closure(kb: Frames, relation: str, max_depth: int = 6,
            known_at: float = KNOWN_AT) -> List[Derived]:
    """Transitive inference over one relation (is_a, part_of, ...):
    every (s, rel, z) reachable by >=2 hops that is not already a fact.
    Each hop is a glyph question kb.ask(x, rel); the derived fact's
    confidence is the product of its hops, and it is emitted only while
    that product clears known_at."""
    subjects = sorted({s for s, r, _ in kb.facts if r == relation})
    out: List[Derived] = []
    for s in subjects:
        seen = {s}
        frontier = [(s, 1.0, [])]
        for depth in range(1, max_depth + 1):
            nxt = []
            for x, c, prem in frontier:
                v = kb.ask(x, relation, known_at=0.0)
                if v.best is None or v.best in seen:
                    continue
                c2 = c * v.conf
                if c2 < known_at:
                    continue
                prem2 = prem + [(x, relation, v.best)]
                seen.add(v.best)
                if depth >= 2 and (s, relation, v.best) not in kb.facts:
                    out.append(Derived((s, relation, v.best), c2, depth, prem2))
                nxt.append((v.best, c2, prem2))
            frontier = nxt
            if not frontier:
                break
    return out


# ── abstraction ─────────────────────────────────────────────────────

def abstract(cases: Sequence[np.ndarray]) -> np.ndarray:
    """The gist of many cases: their bundle. Detail fades, what the
    cases share survives."""
    return bundle(list(cases))


def typical(proto: np.ndarray, role: str, cands: Candidates,
            known_at: float = KNOWN_AT) -> Verdict:
    """'What is typical of this concept for role?' - unbind + cleanup."""
    return judge(bind(proto, R(role)), cands, known_at=known_at)


def classify(g: np.ndarray, prototypes: Dict[str, np.ndarray]) -> Verdict:
    """Nearest prototype. Prototypes are correlated with each other, so
    the random-noise confidence is optimistic here; the margin term is
    what carries the signal (see bench)."""
    return judge(g, Candidates.of_glyphs(prototypes))


# ── composition of conclusions ──────────────────────────────────────

def fact_glyph(s: str, r: str, o: str) -> np.ndarray:
    """A fact as a sentence (memory's/lexicon's form)."""
    return bundle([bind(R("object"), W(o)), bind(R("relation"), W(r)),
                   bind(R("subject"), W(s))])


def slot(role: str, filler: np.ndarray) -> np.ndarray:
    """A COMPOSITE filler in a slot, lexicon's grammar: bind(role,
    roll(filler, 1)). The roll makes nesting ordered (bind alone is
    commutative, so a child's slot would also match its parent)."""
    return bind(R(role), roll(filler, 1))


def unslot(g: np.ndarray, role: str) -> np.ndarray:
    """Inverse of slot(): read a composite filler back out (noisy)."""
    return roll(bind(g, R(role)), -1)


def premises_glyph(premises: Sequence[np.ndarray]) -> np.ndarray:
    """Premises as the language's sequence [p1, p2, ...] = frame
    {#1: p1, #2: p2, ...}, so each premise is addressable."""
    return bundle([slot(f"#{i + 1}", p) for i, p in enumerate(premises)])


def conclude(claim: np.ndarray, premises: Sequence[np.ndarray],
             rule: str, conf: Optional[float] = None) -> np.ndarray:
    """A conclusion is a sentence of the language:
        {claim: <fact glyph>, because: [premise glyphs], rule: <word>,
         confidence: <word>}
    bit-identical to LX.encode of that meaning. It is a glyph, so it can
    be premise #k of the next conclusion. premise(g, k) reads it back."""
    parts = [slot("because", premises_glyph(premises)),
             slot("claim", claim),
             bind(R("rule"), W(rule))]
    if conf is not None:
        parts.insert(1, bind(R("confidence"), W(conf_word(conf))))
    return bundle(parts)


def conf_word(c: float) -> str:
    """Confidence as a word of the language (coarse, decodable)."""
    return ("certain" if c >= 0.99 else "likely" if c >= 0.9 else
            "plausible" if c >= 0.5 else "doubtful")


def premise(g: np.ndarray, k: int = 1) -> np.ndarray:
    """Premise #k of a conclusion glyph (noisy)."""
    return unslot(unslot(g, "because"), f"#{k}")


def claim_of(g: np.ndarray) -> np.ndarray:
    return unslot(g, "claim")


def descend(g: np.ndarray, steps: Sequence[Sequence[str]],
            memory: Dict[str, np.ndarray], known_at: float = KNOWN_AT,
            exclude_path: bool = True) -> Tuple[Optional[str], float, List[str]]:
    """Walk down a nested structure with CLEANUP MEMORY: after each
    step (a list of composite slots to unslot) snap the noisy glyph to the nearest
    glyph in `memory` (e.g. lexicon's named concepts), then continue from
    the clean glyph. Signal therefore never compounds across levels.

    Items already on the path are excluded (exclude_path). Without
    lexicon's roll, bind is symmetric and unbinding a child's roles from
    the child ALSO lands on its parent: measured parent sim 0.32 vs true
    child 0.23. With the roll (slot/unslot) this no longer happens; the
    exclusion stays as a cheap guard. Returns (name, conf, trail)."""
    cands = Candidates.of_glyphs(memory)
    y, trail, conf = g, [], 1.0
    visited = [n for n, v in memory.items() if np.array_equal(v, g)] \
        if exclude_path else []
    for roles in steps:
        x = y
        for r in roles:
            x = unslot(x, r)
        v = judge(x, cands, exclude=visited, known_at=0.0)
        conf *= v.conf
        if v.best is None:
            return None, 0.0, trail
        trail.append(v.best)
        if exclude_path:
            visited.append(v.best)
        y = memory[v.best]
    return (trail[-1] if trail and conf >= known_at else None), conf, trail


def ask_glyph(s: str, r: str) -> np.ndarray:
    """A question in the language: the fact with object '?'."""
    return fact_glyph(s, r, "?")


def answer_glyph(q: np.ndarray, kb: Frames,
                 known_at: float = KNOWN_AT) -> Tuple[Optional[np.ndarray], dict]:
    """Decode a question glyph, answer it, reply with the fact glyph
    (or None + the reason when the answer is not trusted)."""
    sv = judge(bind(q, R("subject")), kb.entities)
    rv = judge(bind(q, R("relation")), Candidates(kb.relations.names, W))
    info = {"subject": sv.to_json(), "relation": rv.to_json()}
    if not (sv.known and rv.known):
        info["status"] = "unparsed"
        return None, info
    v = kb.ask(sv.answer, rv.answer, known_at=known_at)
    info["answer"] = v.to_json()
    if not v.known:
        info["status"] = "unknown"
        return None, info
    info["status"] = "known"
    return fact_glyph(sv.answer, rv.answer, v.answer), info


# ── inference over an ordered parameter ─────────────────────────────

# Empirical P(correct) of each ordinal rule, measured by reasoner/bench.py
# (E7, rng seed 7) on memory's world; conclusions carry these as their
# confidence. First guess was extrapolate 0.90 with decay 0.97 per step;
# E7 measured .945 .82 .80 .67 .40 at depth 1..5 (overconfident), so the
# decay was refit to 0.87. Sandwich: 129/129 correct. reasoner/agent.py
# further updates these from the grades its inferred claims receive.
ORDINAL_RULE_CONF = {"sandwich": 0.98, "extrapolate": 0.94}
EXTRAPOLATE_DECAY = 0.87   # per grid step beyond the last known point


@dataclass
class OrdinalConclusion:
    param: float
    value: str
    conf: float
    rule: str                  # sandwich | extrapolate
    depth: int                 # grid steps from the nearest premise
    premises: List[float]      # params of the known points used


def monotone(points: Dict[float, str]) -> bool:
    """A step function: once the value changes it never comes back."""
    seq = [points[k] for k in sorted(points)]
    seen, last = set(), None
    for v in seq:
        if v != last:
            if v in seen:
                return False
            seen.add(v)
            last = v
    return True


def ordinal_infer(points: Dict[float, str], grid: Sequence[float],
                  min_points: int = 3,
                  rule_conf: Optional[Dict[str, float]] = None
                  ) -> List[OrdinalConclusion]:
    """New facts about unmeasured grid points of a family f(param).

    If the known points form a monotone step function:
      sandwich     f(lo) == f(hi) = v and lo < x < hi  =>  f(x) = v
      extrapolate  x beyond the last known point      =>  f(x) = f(last)
                   (a chain: each grid step is one more inference, so
                   conf decays per step)
    Points where the neighbours disagree get NO conclusion: that is the
    boundary, and saying 'I don't know' there is the calibrated answer.
    """
    rc = rule_conf or ORDINAL_RULE_CONF
    if len(points) < min_points or not monotone(points):
        return []
    known = sorted(points)
    out = []
    for x in sorted(grid):
        if x in points:
            continue
        lo = [k for k in known if k < x]
        hi = [k for k in known if k > x]
        if lo and hi:
            a, b = lo[-1], hi[0]
            if points[a] == points[b]:
                out.append(OrdinalConclusion(x, points[a], rc["sandwich"],
                                             "sandwich", 1, [a, b]))
        elif lo or hi:
            edge = lo[-1] if lo else hi[0]
            steps = sum(1 for g in grid if min(edge, x) < g <= max(edge, x))
            # the edge value must be a plateau (seen twice) to extrapolate
            side = known[-2:] if lo else known[:2]
            if len(side) == 2 and points[side[0]] == points[side[1]]:
                c = rc["extrapolate"] * EXTRAPOLATE_DECAY ** (steps - 1)
                out.append(OrdinalConclusion(x, points[edge], c,
                                             "extrapolate", steps, list(side)))
    return out
