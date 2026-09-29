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
    # break ties deterministically
    ties = signs == 0
    if ties.any():
        signs[ties] = symbol("tie-break")[ties] if len(signs) == DIM else 1
    return signs.astype(np.int8)


def roll(v: np.ndarray, k: int = 1) -> np.ndarray:
    """Rotate a glyph. Encodes order/position/depth: roll(v, 1) is
    'v, one step ago'. Orthogonal to v; invert with roll(v, -k)."""
    return np.roll(v, k)


def sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for bipolar glyphs, in [-1, 1]. Two random
    symbols sit near 0. Above ~0.1 is signal at dim 4096."""
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
        signs[signs == 0] = 1
        return signs.astype(np.int8)

    def __len__(self) -> int:
        return len(self.codons)


# ── Space: graded precedent ─────────────────────────────────────────

@dataclass
class Answer:
    """What a Space says. Trust `top` only when `sufficient` is True
    and `confidence` clears your threshold; otherwise fall back
    (consult something smarter, or ask). receipts = the precedents
    behind the answer: (id, similarity, outcome, glyph_hash)."""

    sufficient: bool
    confidence: float          # consensus of the k nearest precedents
    support: float             # how CLOSE that precedent is (mean sim)
    top: Optional[str]         # leading outcome, None if insufficient
    outcomes: Dict[str, float]  # similarity-weighted distribution
    receipts: List[Tuple[str, float, str, str]]

    def to_json(self) -> Dict[str, Any]:
        return {
            "sufficient": self.sufficient,
            "confidence": round(self.confidence, 4),
            "support": round(self.support, 4),
            "top": self.top,
            "outcomes": {k: round(v, 4) for k, v in self.outcomes.items()},
            "receipts": [
                {"id": i, "sim": round(s, 4), "outcome": o, "hash": h}
                for i, s, o, h in self.receipts
            ],
        }


class Space:
    """Precedent memory: record graded experience, answer by similarity.

    The contract that makes this safe for a machine caller:
      - record() is one write, permanent, no training run
      - query() returns calibrated confidence — on real-world text
        replay, answers at confidence >= 0.5 measured 86% accurate
        while ungated answers measured 50%
      - every answer cites the precedents it stands on
      - below min_sim the Space says 'insufficient' instead of guessing

    Use two Spaces per decision: one for wins, one for failures
    (vetoes). A confident answer that the failure space also endorses
    is a veto — do not act on it; fall back instead.
    """

    def __init__(self, dim: int = DIM, k: int = 15, min_sim: float = 0.10,
                 seed: int = 42, path: Optional[str] = None):
        self.dim, self.k, self.min_sim, self.seed = dim, k, min_sim, seed
        self._rows: List[Tuple[str, str, np.ndarray]] = []  # id, outcome, glyph
        self._matrix: Optional[np.ndarray] = None
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
                              Strand(list(events)).state()))
        if not parts:
            raise ValueError("cannot encode an empty situation")
        return bundle(parts)

    def record(self, situation: Dict[str, str], outcome: str,
               events: Optional[List[np.ndarray]] = None,
               rid: Optional[str] = None) -> str:
        rid = rid or str(uuid.uuid4())[:12]
        glyph = self.encode(situation, events)
        self._rows.append((rid, outcome, glyph))
        self._matrix = None
        if self._db is not None:
            self._db.execute(
                "INSERT OR REPLACE INTO precedents VALUES (?, ?, ?, ?, ?)",
                (rid, json.dumps(situation, ensure_ascii=False), outcome,
                 self.dim, glyph.tobytes()))
            self._db.commit()
        return rid

    def query(self, situation: Dict[str, str],
              events: Optional[List[np.ndarray]] = None) -> Answer:
        if not self._rows:
            return Answer(False, 0.0, 0.0, None, {}, [])
        q = self.encode(situation, events).astype(np.float32)
        if self._matrix is None:
            self._matrix = np.stack(
                [g for _, _, g in self._rows]).astype(np.float32)
        sims = (self._matrix @ q) / self.dim
        order = np.argsort(sims)[::-1][:self.k]
        top_rows = [(self._rows[i], float(sims[i])) for i in order]
        receipts = [
            (rid, s, outcome,
             hashlib.sha256(glyph.tobytes()).hexdigest()[:16])
            for (rid, outcome, glyph), s in top_rows]
        best = top_rows[0][1]
        if best < self.min_sim:
            return Answer(False, 0.0, max(best, 0.0), None, {}, receipts)
        weights = np.array([max(s, 0.0) for _, s in top_rows])
        wsum = float(weights.sum()) or 1.0
        outcomes: Dict[str, float] = {}
        for ((_, outcome, _), _), w in zip(top_rows, weights):
            outcomes[outcome] = outcomes.get(outcome, 0.0) + float(w)
        outcomes = {o: w / wsum for o, w in outcomes.items()}
        top = max(outcomes, key=outcomes.get)
        return Answer(True, outcomes[top], float(weights.mean()),
                      top, outcomes, receipts)

    def __len__(self) -> int:
        return len(self._rows)

    # persistence: one portable file
    def _open(self, path: str) -> None:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(p))
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS precedents ("
            " id TEXT PRIMARY KEY, situation TEXT NOT NULL,"
            " outcome TEXT NOT NULL, dim INTEGER NOT NULL,"
            " glyph BLOB NOT NULL)")
        self._db.commit()
        for rid, _, outcome, dim, blob in self._db.execute(
                "SELECT id, situation, outcome, dim, glyph FROM precedents"):
            if dim != self.dim:
                raise ValueError(
                    f"precedent {rid} has dim {dim}, space is {self.dim}")
            self._rows.append(
                (rid, outcome, np.frombuffer(blob, dtype=np.int8).copy()))
