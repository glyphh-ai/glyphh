"""
glyphh kernel — the AI-native kernel. Single file, numpy + stdlib only.

This is software whose user is a model. There is no UI, no service, no
config. If you are an agent reading this: call spec() — or read SPEC
below — before using the kernel. The file carries its own manual so
the guidance can never be separated from the code.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

DIM = 4096  # default dimensionality; ~1e-3 cross-talk between random symbols
ENCODING = 2  # bump when encode() changes; stores re-encode on open

SPEC = """\
glyphh kernel — substrate guidance for the agent using it

WHAT THIS IS. Your state and execution layer beyond the context
window. Contexts are mortal; the SQLite files a Space writes are not.
Record graded experience as you work; the next context (yours or
another agent's) reopens the files and inherits ground truth instead
of prose about it.

THE FIVE PRIMITIVES. All glyphs are bipolar +/-1 vectors of one fixed
dimension (default 4096); every operation returns the type it takes,
so composites nest indefinitely.
  symbol(key, seed=42, dim)  deterministic glyph: same inputs -> the
      identical vector on any machine, forever. Shared seed = shared
      vocabulary between agents; different seeds are mutual noise.
  bind(a, b)     associate (elementwise multiply). Self-inverse; the
      result resembles neither input. Use for role-filler pairs.
  bundle(parts)  superpose (majority vote); resembles ALL inputs.
      Order-free: the same parts in any order give the same glyph.
      Capacity is finite: past a few dozen parts detail fades and gist
      survives — that is abstraction; keep receipts for the detail.
  roll(v, k)     rotate: order, position, depth. Undo with roll(v,-k).
  sim(a, b)      cosine in [-1, 1]. Random glyphs sit near 0. For
      situations, sim tracks the FRACTION OF SHARED ATTRIBUTE PAIRS,
      whichever attributes they are (measured, 4 attributes: sharing
      1/2/3 -> 0.14/0.28/0.44; 2 attributes sharing 1 -> 0.25), even
      when the shared attributes are decision-irrelevant.

THE TWO CONSTRUCTS.
  Strand: ordered meaning. append() glyphs; state(decay) folds the
      sequence into one glyph where recent items dominate and order
      matters. Detail recoverable a few steps back; the KIND of
      trajectory recognizable much longer.
  Space(dim, k, min_sim, seed, decay, author, path): graded precedent.
      record(situation, outcome, events=None, ts=None) — one write,
      permanent, time-stamped.
      query(...) -> Answer(sufficient, confidence, support, count,
      top, outcomes, receipts); only precedents clearing min_sim vote.
      answers(...) -> [Evidence] for EVERY outcome with qualifying
      precedent: the read for situations with more than one true
      outcome. evidence(situation, outcome) grades one candidate.
      matches(situation, outcome) — max sim among precedents with THAT
      outcome: the veto primitive, undilutable by consensus.
      refresh() pulls rows other agents wrote to a shared WAL file;
      merge(other_path) unions another Space file by id, authors kept.

THE CONTRACT: NOTHING UNGRADED. Route every domain decision through
decide(wins, vetoes, situation, events) -> Decision. It is:
  a = wins.query(situation, events)
  if a.sufficient and a.confidence >= 0.5 and a.count >= 3:
      if not vetoed(a.top):               # see rule 3
          act(a.top)                      # reflex: free, cited
      else: consult fallback              # vetoed
  else: consult fallback                  # insufficient precedent
  success = the WORLD grades the action   # never self-graded
  (wins if success else vetoes).record(situation, action, events)
Fallback chain by cost: reflex (free) -> consultant (paid) -> human
(last resort; the answer is itself a grade). Consult rate should fall
over the Space's life — that curve is the product metric.

RULES THAT DECIDE WHETHER IT WORKS.
  1. Trust needs three gates: sufficient (similarity), confidence
     (consensus), count (population). A consensus of one is
     confidence 1.0 and means almost nothing — gate count >= 3.
  2. Attribute hygiene: encode ONLY decision-relevant attributes;
     incidental ones (ids, regions, timestamps) poison neighborhoods.
     Size min_sim as the attribute-overlap fraction that should count
     as 'the same kind of situation'.
  3. Vetoes suppress, they don't erase, and the newest evidence wins:
     a reflex is blocked while a recorded failure sits as close as the
     wins recommending it AND is newer than the newest such win. A
     later reproduction lifts an older veto; a later failure
     re-imposes it. After drift, expect a few wrong firings while
     failures arrive. Use matches(), never a consensus vote, for
     vetoes. decide(min_veto_count=2) demands corroborated failures:
     harder to sabotage, slower to stop.
  4. One question, several true answers: when a situation genuinely
     has many outcomes (a file imports five modules), confidence
     splits across them and no single one clears 0.5. That is not
     disagreement. Read answers() and gate each outcome on its own
     count instead of on its share.
  5. Precedent never overrides a proof: auth, money conservation,
     state-machine legality stay hand-written.

MORE THAN ONE AGENT. Private kernel per agent; one shared kernel per
team, author= set so receipts show who grounded what. Share a file
live (WAL + refresh) or ship and merge(). Verify before you trust:
replay incoming receipts against your own world before merging.
Meaning is operational at every scale: a concept is meaningful exactly
to the degree its glyph's neighborhood predicts the world; a
teammate's precedent is trustworthy exactly to the degree its
receipts replay.

STORES OUTLIVE ENCODINGS. Every file records the encoding it was
written under. Opening (or merging) a file from an older encoding
re-encodes its glyphs from the stored situations and events, so old
precedent keeps matching fresh queries. Events are stored with each
precedent, so re-encoding is lossless (rows written before events
were stored re-encode without their trajectory).
"""


def spec() -> str:
    """The substrate guidance. An agent that imports this kernel cold
    should read spec() before recording or querying anything."""
    return SPEC


def reencode_store(path: str, dim: int = DIM, k: int = 15,
                   min_sim: float = 0.10, seed: int = 42,
                   decay: float = 0.7) -> int:
    """Re-encode every precedent's glyph from its stored situation and
    events, under the current encoding, and stamp the file with it.
    Opening a Space does this automatically for files from an older
    encoding; call it directly to force a rebuild (e.g. after changing
    seed or decay). Returns rows re-encoded.

    Rows recorded before events were persisted re-encode without their
    trajectory component."""
    db = sqlite3.connect(str(Path(path).expanduser()))
    _ensure_schema(db)
    space = Space(dim=dim, k=k, min_sim=min_sim, seed=seed, decay=decay)
    n = _reencode_rows(db, space)
    db.commit()
    db.close()
    return n


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


def _tiebreak(parts: Sequence[np.ndarray]) -> np.ndarray:
    """Tie-break vector for a majority vote: a pseudo-random glyph
    seeded by the hash of the parts as a SET (their bytes, sorted).

    Why this shape. A shared global tie-break vector injects a common
    component into every even-count bundle, so unrelated small
    situations look alike. Deriving it from one part (encoding 1 used
    roll(parts[0])) made similarity depend on which attribute differed:
    changing the attribute that sorts first cost twice as much as
    changing the one that sorts last (0.26 vs 0.50 at two attributes).
    A hash of the whole multiset is deterministic, different for every
    distinct input, uncorrelated with any single part, and independent
    of part order — so tied positions carry no bias at all."""
    h = hashlib.sha256()
    for b in sorted(np.ascontiguousarray(p).tobytes() for p in parts):
        h.update(b)
    rng = np.random.RandomState(np.frombuffer(h.digest()[:4], dtype=np.uint32))
    return (rng.randint(0, 2, len(parts[0]), dtype=np.int8) * 2 - 1)


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
    if ties.any():
        signs[ties] = _tiebreak(parts)[ties]
    return signs.astype(np.int8)


def roll(v: np.ndarray, k: int = 1) -> np.ndarray:
    """Rotate a glyph. Encodes order/position/depth: roll(v, 1) is
    'v, one step ago'. Orthogonal to v; invert with roll(v, -k)."""
    return np.roll(v, k)


def sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for bipolar glyphs, in [-1, 1]. Two random
    symbols sit near 0. For situation glyphs, sim approximately tracks
    the FRACTION OF SHARED ATTRIBUTE PAIRS — two 4-attribute
    situations sharing 3 attributes measure ~0.44, not ~0."""
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
        rolled = []
        for age, codon in enumerate(reversed(self.codons)):
            shifted = roll(codon, age)
            rolled.append(shifted)
            acc += (decay ** age) * shifted.astype(np.float64)
        signs = np.sign(acc)
        ties = signs == 0
        if ties.any():
            signs[ties] = _tiebreak(rolled)[ties]
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


@dataclass
class Evidence:
    """How well one outcome is supported in one situation, judged on
    its own — not as a share of a vote. `count` precedents with this
    outcome clear min_sim, at mean similarity `support` (nearest:
    `nearest`); the newest of them was recorded at `latest` (epoch
    seconds, 0.0 for rows written before time-stamping)."""

    outcome: str
    count: int
    support: float
    nearest: float
    latest: float
    authors: List[str]

    def to_json(self) -> Dict[str, Any]:
        return {"outcome": self.outcome, "count": self.count,
                "support": round(self.support, 4),
                "nearest": round(self.nearest, 4),
                "latest": self.latest, "authors": self.authors}


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
    shared attributes means min_sim ~0.4 (sharing 2 measures ~0.28),
    and the default 0.10 only excludes near-strangers.
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
        self._ts: List[float] = []
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
                author: str, ts: float) -> None:
        self._ids.append(rid)
        self._outcomes.append(outcome)
        self._authors.append(author)
        self._ts.append(float(ts))
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
               rid: Optional[str] = None,
               ts: Optional[float] = None) -> str:
        rid = rid or str(uuid.uuid4())[:12]
        ts = time.time() if ts is None else float(ts)
        glyph = self.encode(situation, events)
        self._append(rid, outcome, glyph, self.author, ts)
        if self._db is not None:
            blob = (np.stack(events).astype(np.int8).tobytes()
                    if events else None)
            self._db.execute(
                "INSERT OR REPLACE INTO precedents (id, situation, outcome,"
                " dim, glyph, author, ts, events)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (rid, json.dumps(situation, ensure_ascii=False), outcome,
                 self.dim, glyph.tobytes(), self.author, ts, blob))
            self._db.commit()
        return rid

    def _sims(self, situation: Dict[str, str],
              events: Optional[List[np.ndarray]]) -> np.ndarray:
        q = self.encode(situation, events).astype(np.float32)
        return (self._matrix[:self._n] @ q) / self.dim

    def _top(self, situation: Dict[str, str],
             events: Optional[List[np.ndarray]]) -> List[Tuple[int, float]]:
        sims = self._sims(situation, events)
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

    def _evidence(self, sims: np.ndarray, outcome: str,
                  bar: float) -> Evidence:
        idx = [i for i in range(self._n)
               if self._outcomes[i] == outcome and sims[i] >= bar]
        if not idx:
            return Evidence(outcome, 0, 0.0, 0.0, 0.0, [])
        close = sims[idx]
        return Evidence(outcome, len(idx), float(close.mean()),
                        float(close.max()),
                        max(self._ts[i] for i in idx),
                        sorted({self._authors[i] for i in idx}))

    def evidence(self, situation: Dict[str, str], outcome: str,
                 events: Optional[List[np.ndarray]] = None,
                 min_sim: Optional[float] = None) -> Evidence:
        """Support for ONE candidate outcome, over every precedent (not
        just the top k), judged on its own: how many precedents with
        this outcome clear the bar, how close, how recent, by whom."""
        if self._n == 0:
            return Evidence(outcome, 0, 0.0, 0.0, 0.0, [])
        bar = self.min_sim if min_sim is None else min_sim
        return self._evidence(self._sims(situation, events), outcome, bar)

    def answers(self, situation: Dict[str, str],
                events: Optional[List[np.ndarray]] = None,
                min_count: int = 1) -> List[Evidence]:
        """Every outcome with qualifying precedent in this situation,
        strongest first. The read for situations that genuinely have
        several true outcomes: gate each on its own count, not on its
        share of a vote (see SPEC rule 4)."""
        if self._n == 0:
            return []
        sims = self._sims(situation, events)
        found = {self._outcomes[i] for i in range(self._n)
                 if sims[i] >= self.min_sim}
        out = [self._evidence(sims, o, self.min_sim) for o in found]
        out = [e for e in out if e.count >= min_count]
        return sorted(out, key=lambda e: (-e.count, -e.support, e.outcome))

    def matches(self, situation: Dict[str, str], outcome: str,
                events: Optional[List[np.ndarray]] = None) -> float:
        """Max similarity among precedents with THIS outcome (0.0 if
        none). The veto primitive: 'how close is the nearest recorded
        failure of this exact action?' — a direct check that no
        consensus vote can dilute."""
        if self._n == 0:
            return 0.0
        mask = np.array([o == outcome for o in self._outcomes[:self._n]])
        if not mask.any():
            return 0.0
        sims = self._sims(situation, events)[mask]
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
        _ensure_schema(self._db)
        if _file_encoding(self._db) < ENCODING:
            _reencode_rows(self._db, self)
        self._db.commit()
        self.refresh()

    def refresh(self) -> int:
        """Pull in rows other agents wrote to this file since open.
        Returns how many new precedents arrived."""
        if self._db is None:
            return 0
        known = set(self._ids)
        added = 0
        for rid, outcome, dim, blob, author, ts in self._db.execute(
                "SELECT id, outcome, dim, glyph, author, ts "
                "FROM precedents ORDER BY ts, rowid"):
            if rid in known:
                continue
            if dim != self.dim:
                raise ValueError(
                    f"precedent {rid} has dim {dim}, space is {self.dim}")
            self._append(rid, outcome,
                         np.frombuffer(blob, dtype=np.int8).copy(),
                         author, ts)
            added += 1
        return added

    def merge(self, other_path: str) -> int:
        """Union another Space file into this one (by precedent id).
        The exchange primitive between agents: ship the file, verify
        its receipts against your own world, then merge. Rows from a
        file written under an older encoding are re-encoded from their
        situations on the way in. Returns how many precedents were
        new."""
        other = sqlite3.connect(str(Path(other_path).expanduser()))
        cols = [r[1] for r in other.execute("PRAGMA table_info(precedents)")]
        stale = _file_encoding(other) < ENCODING
        select = "SELECT id, situation, outcome, dim, glyph, {a}, {t}, {e} " \
                 "FROM precedents".format(
                     a="author" if "author" in cols else "'anon'",
                     t="ts" if "ts" in cols else "0.0",
                     e="events" if "events" in cols else "NULL")
        known = set(self._ids)
        added = 0
        for rid, situation, outcome, dim, blob, author, ts, ev in \
                other.execute(select):
            if rid in known:
                continue
            if dim != self.dim:
                raise ValueError(
                    f"precedent {rid} has dim {dim}, space is {self.dim}")
            if stale:
                glyph = self.encode(json.loads(situation),
                                    _events_from_blob(ev, dim))
            else:
                glyph = np.frombuffer(blob, dtype=np.int8).copy()
            self._append(rid, outcome, glyph, author, ts)
            if self._db is not None:
                self._db.execute(
                    "INSERT OR REPLACE INTO precedents (id, situation,"
                    " outcome, dim, glyph, author, ts, events)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (rid, situation, outcome, dim, glyph.tobytes(), author,
                     ts, ev))
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


# ── the contract as a function ──────────────────────────────────────

@dataclass
class Decision:
    """What decide() concluded. Act on `outcome` only when `act`.

    reason: 'reflex' (act), 'insufficient' (nothing clears min_sim),
    'uncalibrated' (fewer than min_count precedents), 'low_confidence'
    (no consensus), or 'vetoed' (a recorded failure is as close as the
    wins and newer than them). `lifted` is True when a close veto
    exists but a newer win outranks it."""

    act: bool
    outcome: Optional[str]
    reason: str
    answer: Answer
    veto: Optional[Evidence]
    lifted: bool

    def to_json(self) -> Dict[str, Any]:
        return {"act": self.act, "outcome": self.outcome,
                "reason": self.reason, "lifted": self.lifted,
                "veto": self.veto.to_json() if self.veto else None,
                "answer": self.answer.to_json()}


def decide(wins: Space, vetoes: Space, situation: Dict[str, str],
           events: Optional[List[np.ndarray]] = None, *,
           min_confidence: float = 0.5, min_count: int = 3,
           min_veto_count: int = 1) -> Decision:
    """THE CONTRACT (see SPEC): the three trust gates on the wins, then
    the veto check, with the newest evidence winning.

    A veto of the top outcome counts when a recorded failure is at
    least as close as the wins recommending it (sim >= answer.support).
    It blocks while at least `min_veto_count` such failures exist AND
    the newest of them is newer than the newest qualifying win; a later
    reproduction lifts it. min_veto_count=1 is fail-closed (one failure
    stops the reflex); 2+ demands corroboration (harder to sabotage)."""
    answer = wins.query(situation, events)
    if not answer.sufficient:
        return Decision(False, None, "insufficient", answer, None, False)
    top = answer.top
    veto = vetoes.evidence(situation, top, events,
                           min_sim=max(answer.support, 1e-9))
    win = wins.evidence(situation, top, events)
    close = veto.count >= min_veto_count
    lifted = close and win.latest > veto.latest
    if close and not lifted:
        return Decision(False, top, "vetoed", answer, veto, False)
    if answer.count < min_count:
        return Decision(False, top, "uncalibrated", answer,
                        veto if veto.count else None, lifted)
    if answer.confidence < min_confidence:
        return Decision(False, top, "low_confidence", answer,
                        veto if veto.count else None, lifted)
    return Decision(True, top, "reflex", answer,
                    veto if veto.count else None, lifted)


# ── store schema and migration ──────────────────────────────────────

def _ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS precedents ("
        " id TEXT PRIMARY KEY, situation TEXT NOT NULL,"
        " outcome TEXT NOT NULL, dim INTEGER NOT NULL,"
        " glyph BLOB NOT NULL, author TEXT NOT NULL DEFAULT 'anon',"
        " ts REAL NOT NULL DEFAULT 0, events BLOB)")
    db.execute("CREATE TABLE IF NOT EXISTS meta ("
               " key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    cols = [r[1] for r in db.execute("PRAGMA table_info(precedents)")]
    # migrate older files in place
    if "author" not in cols:
        db.execute("ALTER TABLE precedents ADD COLUMN author "
                   "TEXT NOT NULL DEFAULT 'anon'")
    if "ts" not in cols:
        db.execute("ALTER TABLE precedents ADD COLUMN ts "
                   "REAL NOT NULL DEFAULT 0")
    if "events" not in cols:
        db.execute("ALTER TABLE precedents ADD COLUMN events BLOB")
    rows = db.execute("SELECT COUNT(*) FROM precedents").fetchone()[0]
    stamped = db.execute(
        "SELECT value FROM meta WHERE key = 'encoding'").fetchone()
    if stamped is None:
        # an empty file starts on the current encoding; a populated
        # file without a stamp predates stamping (encoding 1)
        db.execute("INSERT INTO meta VALUES ('encoding', ?)",
                   (str(ENCODING if rows == 0 else 1),))


def _file_encoding(db: sqlite3.Connection) -> int:
    try:
        row = db.execute(
            "SELECT value FROM meta WHERE key = 'encoding'").fetchone()
    except sqlite3.Error:
        row = None
    if row is not None:
        return int(row[0])
    try:
        rows = db.execute("SELECT COUNT(*) FROM precedents").fetchone()[0]
    except sqlite3.Error:
        rows = 0
    return ENCODING if rows == 0 else 1


def _events_from_blob(blob: Optional[bytes],
                      dim: int) -> Optional[List[np.ndarray]]:
    if not blob:
        return None
    flat = np.frombuffer(blob, dtype=np.int8)
    return [row.copy() for row in flat.reshape(-1, dim)]


def _reencode_rows(db: sqlite3.Connection, space: "Space") -> int:
    rows = db.execute(
        "SELECT id, situation, dim, events FROM precedents").fetchall()
    done = 0
    for rid, situation_json, dim, ev in rows:
        try:
            glyph = space.encode(json.loads(situation_json),
                                 _events_from_blob(ev, space.dim))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue  # no usable situation stored: keep the old glyph
        db.execute("UPDATE precedents SET glyph = ?, dim = ? WHERE id = ?",
                   (glyph.tobytes(), space.dim, rid))
        done += 1
    db.execute("INSERT OR REPLACE INTO meta VALUES ('encoding', ?)",
               (str(ENCODING),))
    return done
