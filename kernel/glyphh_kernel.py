"""
glyphh kernel — the AI-native kernel. Single file, numpy + stdlib only.

This is software whose user is a model. There is no UI, no service, no
config. There are five primitives, two constructs, and one contract:

  primitives   symbol · bind · bundle · roll · sim
  constructs   Strand (ordered meaning) · Space (graded precedent)
  contract     nothing enters a Space ungraded; every answer carries
               receipts; confidence tells the caller when to trust it.

State is a SQLite file the agent can carry, diff, merge, and hand to
another agent. The full semantics is in KERNEL.md, written for a model
reader. The spec is the interface.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

DIM = 4096  # default dimensionality; ~1e-3 cross-talk between random symbols


# ── primitives ──────────────────────────────────────────────────────

def symbol(key: str, seed: int = 42, dim: int = DIM) -> np.ndarray:
    """Deterministic bipolar (+1/-1) symbol for a key.

    Same (key, seed, dim) -> identical vector, on any machine, forever.
    Shared seeds are shared vocabulary; different seeds are mutually
    random noise. This is how two agents agree on meaning.
    """
    digest = hashlib.sha256(f"{seed}:{key}".encode()).digest()
    rng = np.random.RandomState(np.frombuffer(digest[:4], dtype=np.uint32))
    return (rng.randint(0, 2, dim, dtype=np.int8) * 2 - 1)


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Associate two glyphs (elementwise multiply). Self-inverse:
    bind(bind(a, b), b) == a. The result resembles neither input."""
    return (a * b).astype(np.int8)


def bundle(parts: Sequence[np.ndarray]) -> np.ndarray:
    """Superpose glyphs (majority vote). The result resembles ALL
    inputs. Capacity is finite: past a few dozen items, individual
    contributions fade — detail dies, gist survives. That is
    abstraction, not failure; keep receipts if you need the detail."""
    if not parts:
        raise ValueError("cannot bundle nothing")
    total = np.sum(np.stack(parts).astype(np.int32), axis=0)
    signs = np.sign(total)
    ties = signs == 0
    if ties.any():  # deterministic, unbiased, works at any dimension
        signs[ties] = symbol("tie-break", 0, len(signs))[ties]
    return signs.astype(np.int8)


def roll(v: np.ndarray, k: int = 1) -> np.ndarray:
    """Rotate a glyph. Encodes order/position/depth: roll(v, 1) is
    'v, one step ago'. Orthogonal to v; invert with roll(v, -k)."""
    return np.roll(v, k)


def sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for bipolar glyphs, in [-1, 1]. Two random
    symbols sit near 0. For situation glyphs, sim approximately tracks
    the FRACTION OF SHARED ATTRIBUTE PAIRS — two 4-attribute
    situations sharing 2 attributes measure ~0.4-0.5, not ~0."""
    return float(np.dot(a.astype(np.float32), b.astype(np.float32))) / len(a)


# ── Strand: ordered meaning ─────────────────────────────────────────

class Strand:
    """A sequence of glyphs whose ORDER is part of the meaning.

    state() folds the sequence into one glyph: each codon is rotated
    by its age and decayed, so recent items dominate and order is
    preserved — two strands with the same items in different order
    have different states. Detail survives ~3 steps; the gist of
    'what kind of trajectory is this' survives far longer.
    """

    def __init__(self, codons: Optional[List[np.ndarray]] = None):
        self.codons: List[np.ndarray] = list(codons or [])

    def append(self, codon: np.ndarray) -> "Strand":
        self.codons.append(codon)
        return self

    def state(self, decay: float = 0.7) -> np.ndarray:
        if not self.codons:
            raise ValueError("empty strand has no state")
        acc = np.zeros(len(self.codons[0]), dtype=np.float64)
        for age, codon in enumerate(reversed(self.codons)):
            acc += (decay ** age) * roll(codon, age).astype(np.float64)
        signs = np.sign(acc)
        ties = signs == 0
        if ties.any():
            signs[ties] = symbol("tie-break", 0, len(signs))[ties]
        return signs.astype(np.int8)

    def __len__(self) -> int:
        return len(self.codons)


# ── Space: graded precedent ─────────────────────────────────────────

@dataclass
class Answer:
    """What a Space says. Trust `top` only when `sufficient` is True
    AND `confidence` clears your threshold AND `count` is more than a
    couple — a consensus of one is not consensus. receipts = the
    precedents behind the answer: (id, similarity, outcome, hash)."""

    sufficient: bool
    confidence: float          # consensus among qualifying precedents
    support: float             # how CLOSE they are (mean similarity)
    count: int                 # how many precedents cleared min_sim
    top: Optional[str]         # leading outcome, None if insufficient
    outcomes: Dict[str, float]  # similarity-weighted distribution
    receipts: List[Tuple[str, float, str, str, str]]  # +author

    def to_json(self) -> Dict[str, Any]:
        return {
            "sufficient": self.sufficient,
            "confidence": round(self.confidence, 4),
            "support": round(self.support, 4),
            "count": self.count,
            "top": self.top,
            "outcomes": {k: round(v, 4) for k, v in self.outcomes.items()},
            "receipts": [
                {"id": i, "sim": round(s, 4), "outcome": o, "hash": h,
                 "author": a}
                for i, s, o, h, a in self.receipts
            ],
        }


class Space:
    """Precedent memory: record graded experience, answer by similarity.

    The contract that makes this safe for a machine caller:
      - record() is one write, permanent, no training run
      - query() returns calibrated confidence over the precedents that
        clear min_sim — rows below the bar carry no vote
      - every answer cites the precedents it stands on
      - with nothing above min_sim the Space says 'insufficient'
        instead of guessing

    Encode ONLY decision-relevant attributes: sim tracks attribute
    overlap, so incidental attributes (region, timestamps, ids) make
    unrelated situations look alike and poison neighborhoods. Set
    min_sim to the overlap fraction that should count as 'the same
    kind of situation' — with a 4-attribute situation, requiring 3
    shared attributes means min_sim ~0.5-0.75, and the default 0.10
    only excludes near-strangers.
    """

    def __init__(self, dim: int = DIM, k: int = 15, min_sim: float = 0.10,
                 seed: int = 42, decay: float = 0.7, author: str = "anon",
                 path: Optional[str] = None):
        self.dim, self.k, self.min_sim, self.seed = dim, k, min_sim, seed
        self.decay = decay
        self.author = author
        self._ids: List[str] = []
        self._outcomes: List[str] = []
        self._authors: List[str] = []
        self._glyphs: List[np.ndarray] = []
        self._matrix = np.empty((0, dim), dtype=np.float32)  # grown 2x
        self._n = 0
        self._db = None
        if path:
            self._open(path)

    # encoding: a situation is a dict of attributes; optional events
    # fold in as a strand so order-carrying situations keep their order
    def encode(self, situation: Dict[str, str],
               events: Optional[List[np.ndarray]] = None) -> np.ndarray:
        parts = [bind(symbol(f"attr:{a}", self.seed, self.dim),
                      symbol(f"val:{v}", self.seed, self.dim))
                 for a, v in sorted(situation.items())]
        if events:
            parts.append(bind(symbol("trajectory", self.seed, self.dim),
                              Strand(list(events)).state(self.decay)))
        if not parts:
            raise ValueError("cannot encode an empty situation")
        return bundle(parts)

    def _append(self, rid: str, outcome: str, glyph: np.ndarray,
                author: str) -> None:
        self._ids.append(rid)
        self._outcomes.append(outcome)
        self._authors.append(author)
        self._glyphs.append(glyph)
        if self._n == len(self._matrix):  # amortized O(1) growth
            grown = np.empty((max(64, 2 * len(self._matrix)), self.dim),
                             dtype=np.float32)
            grown[:self._n] = self._matrix[:self._n]
            self._matrix = grown
        self._matrix[self._n] = glyph.astype(np.float32)
        self._n += 1

    def record(self, situation: Dict[str, str], outcome: str,
               events: Optional[List[np.ndarray]] = None,
               rid: Optional[str] = None) -> str:
        rid = rid or str(uuid.uuid4())[:12]
        glyph = self.encode(situation, events)
        self._append(rid, outcome, glyph, self.author)
        if self._db is not None:
            self._db.execute(
                "INSERT OR REPLACE INTO precedents VALUES (?, ?, ?, ?, ?, ?)",
                (rid, json.dumps(situation, ensure_ascii=False), outcome,
                 self.dim, glyph.tobytes(), self.author))
            self._db.commit()
        return rid

    def _top(self, situation: Dict[str, str],
             events: Optional[List[np.ndarray]]) -> List[Tuple[int, float]]:
        q = self.encode(situation, events).astype(np.float32)
        sims = (self._matrix[:self._n] @ q) / self.dim
        order = np.argsort(sims)[::-1][:self.k]
        return [(int(i), float(sims[i])) for i in order]

    def query(self, situation: Dict[str, str],
              events: Optional[List[np.ndarray]] = None) -> Answer:
        if self._n == 0:
            return Answer(False, 0.0, 0.0, 0, None, {}, [])
        top = self._top(situation, events)
        receipts = [
            (self._ids[i], s, self._outcomes[i],
             hashlib.sha256(self._glyphs[i].tobytes()).hexdigest()[:16],
             self._authors[i])
            for i, s in top]
        # only precedents that clear the similarity bar get a vote
        voters = [(i, s) for i, s in top if s >= self.min_sim]
        if not voters:
            return Answer(False, 0.0, max(top[0][1], 0.0), 0,
                          None, {}, receipts)
        weights = np.array([s for _, s in voters])
        wsum = float(weights.sum()) or 1.0
        outcomes: Dict[str, float] = {}
        for (i, _), w in zip(voters, weights):
            outcomes[self._outcomes[i]] = (
                outcomes.get(self._outcomes[i], 0.0) + float(w))
        outcomes = {o: w / wsum for o, w in outcomes.items()}
        top_outcome = max(outcomes, key=outcomes.get)
        return Answer(True, outcomes[top_outcome], float(weights.mean()),
                      len(voters), top_outcome, outcomes, receipts)

    def matches(self, situation: Dict[str, str], outcome: str,
                events: Optional[List[np.ndarray]] = None) -> float:
        """Max similarity among precedents with THIS outcome (0.0 if
        none). The veto primitive: 'how close is the nearest recorded
        failure of this exact action?' — a direct check that no
        consensus vote can dilute."""
        if self._n == 0:
            return 0.0
        q = self.encode(situation, events).astype(np.float32)
        mask = np.array([o == outcome for o in self._outcomes[:self._n]])
        if not mask.any():
            return 0.0
        sims = (self._matrix[:self._n][mask] @ q) / self.dim
        return float(sims.max())

    def __len__(self) -> int:
        return self._n

    # persistence: one portable file; WAL so several agents can share it
    def _open(self, path: str) -> None:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(p), timeout=10.0)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=10000")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS precedents ("
            " id TEXT PRIMARY KEY, situation TEXT NOT NULL,"
            " outcome TEXT NOT NULL, dim INTEGER NOT NULL,"
            " glyph BLOB NOT NULL, author TEXT NOT NULL DEFAULT 'anon')")
        cols = [r[1] for r in self._db.execute(
            "PRAGMA table_info(precedents)")]
        if "author" not in cols:  # migrate pre-author files in place
            self._db.execute("ALTER TABLE precedents ADD COLUMN author "
                             "TEXT NOT NULL DEFAULT 'anon'")
        self._db.commit()
        for rid, _, outcome, dim, blob, author in self._db.execute(
                "SELECT id, situation, outcome, dim, glyph, author "
                "FROM precedents"):
            if dim != self.dim:
                raise ValueError(
                    f"precedent {rid} has dim {dim}, space is {self.dim}")
            self._append(rid, outcome,
                         np.frombuffer(blob, dtype=np.int8).copy(), author)

    def refresh(self) -> int:
        """Pull in rows other agents wrote to this file since open.
        Returns how many new precedents arrived."""
        if self._db is None:
            return 0
        known = set(self._ids)
        added = 0
        for rid, _, outcome, dim, blob, author in self._db.execute(
                "SELECT id, situation, outcome, dim, glyph, author "
                "FROM precedents"):
            if rid in known:
                continue
            if dim != self.dim:
                raise ValueError(
                    f"precedent {rid} has dim {dim}, space is {self.dim}")
            self._append(rid, outcome,
                         np.frombuffer(blob, dtype=np.int8).copy(), author)
            added += 1
        return added

    def merge(self, other_path: str) -> int:
        """Union another Space file into this one (by precedent id).
        The exchange primitive between agents: ship the file, verify
        its receipts against your own world, then merge. Returns how
        many precedents were new."""
        other = sqlite3.connect(str(Path(other_path).expanduser()))
        cols = [r[1] for r in other.execute("PRAGMA table_info(precedents)")]
        select = ("SELECT id, situation, outcome, dim, glyph, author "
                  "FROM precedents" if "author" in cols else
                  "SELECT id, situation, outcome, dim, glyph, 'anon' "
                  "FROM precedents")
        known = set(self._ids)
        added = 0
        for rid, situation, outcome, dim, blob, author in other.execute(select):
            if rid in known:
                continue
            if dim != self.dim:
                raise ValueError(
                    f"precedent {rid} has dim {dim}, space is {self.dim}")
            glyph = np.frombuffer(blob, dtype=np.int8).copy()
            self._append(rid, outcome, glyph, author)
            if self._db is not None:
                self._db.execute(
                    "INSERT OR REPLACE INTO precedents "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (rid, situation, outcome, dim, glyph.tobytes(), author))
            added += 1
        if self._db is not None:
            self._db.commit()
        other.close()
        return added

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self) -> "Space":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
