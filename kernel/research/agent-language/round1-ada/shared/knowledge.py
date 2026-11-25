"""knowledge.py -- the group's shared, graded knowledge base (owner: memory).

    import sys; sys.path.insert(0, "<agents>/shared")
    from knowledge import KB
    kb = KB()                                  # shared files in shared/kb/
    cid = kb.tell("reasoner", "cat", "is_a", "mammal", evidence=[...])
    kb.grade("lexicon", cid, True, how="re-derived from is_a chain")
    b = kb.ask("cat", "is_a", asker="courier")
    b.status   # known | vetoed | contested | uncertain | claimed | unknown
    b.value, b.confidence, b.count, b.receipts, b.pending

A FACT IS A SENTENCE OF THE LANGUAGE. The frame
    {subject: s, relation: r, object: o, **context}
encoded with the shared vocabulary (role = symbol("attr:"+role),
word = symbol("val:"+word), seed 42, dim 4096) is the fact glyph. The
question {subject, relation, **context} is the same frame with the
object role removed, and it is bit-identical to kernel
Space.encode(situation) -- so every question is directly a Space
situation, and the answer (the object) is the Space outcome.

NOTHING UNGRADED, NEVER SELF-GRADED. tell() only files a claim. A claim
becomes knowledge when an agent OTHER than its author grades it:
  ok=True   the grader reproduced it (re-derived, re-measured,
            re-computed in its own world)  -> one win precedent
  ok=False  the grader tried and got something else -> one veto
Each (claim, grader) pair is one precedent, author=grader, so a fact
reproduced by three different agents has count 3 and clears the
kernel's trust gate; a fact only its author believes never does.

Files (all under the KB root, WAL so several processes share them):
  claims.db  kernel Space: every told claim (outcome = object)
  wins.db    kernel Space: one row per (claim, grader) reproduction
  vetoes.db  kernel Space: one row per (claim, grader) refutation
  ledger.db  sqlite: claims, grades, asks (the audit trail; wins and
             vetoes are a projection of it, see rebuild()/audit())
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

_HERE = Path(__file__).resolve().parent
_ADA = _HERE.parent.parent / "kernel_v1"
if str(_ADA) not in sys.path:
    sys.path.insert(0, str(_ADA))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from glyphh_kernel import Space, bind, bundle, sim, symbol  # noqa: E402

SEED, DIM = 42, 4096
DEFAULT_ROOT = _HERE / "kb"

# Trust gates (kernel contract). MIN_SIM sized by measured overlap
# (kernel rule 2): a {subject, relation} question sharing one of its two
# pairs measures ~0.26; 3/4/5-attribute questions differing in ONE
# attribute measure ~0.50/0.61/0.64. A fact KB wants THE SAME question,
# so the default 0.70 admits only exact (or >=6-attribute, one-off)
# matches. Pass KB(min_sim=0.45) for a domain where "same situation up
# to one attribute" should generalize.
MIN_SIM = 0.70
MIN_CONF = 0.5
MIN_COUNT = 3

STATUSES = ("known", "vetoed", "contested", "uncertain", "claimed", "unknown")


class SelfGrade(ValueError):
    """Raised when an agent tries to grade its own claim."""


def _role(r: str) -> np.ndarray:
    return symbol(f"attr:{r}", SEED, DIM)


def _word(w: str) -> np.ndarray:
    return symbol(f"val:{w}", SEED, DIM)


def frame_glyph(frame: Dict[str, str]) -> np.ndarray:
    """Encode a flat frame. Uses lexicon's language module when present
    (so its codebook learns the words); the math is identical to the
    kernel's Space.encode either way."""
    try:
        from language import LX  # type: ignore
        return np.asarray(LX.encode(dict(frame)), dtype=np.int8)
    except Exception:
        parts = [bind(_role(a), _word(v)) for a, v in sorted(frame.items())]
        return bundle(parts)


def fact_frame(subject: str, relation: str, obj: str,
               context: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    f = {"subject": str(subject), "relation": str(relation),
         "object": str(obj)}
    for k, v in (context or {}).items():
        f[str(k)] = str(v)
    return f


def question_frame(subject: str, relation: str,
                   context: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    f = {"subject": str(subject), "relation": str(relation)}
    for k, v in (context or {}).items():
        f[str(k)] = str(v)
    return f


@dataclass
class Claim:
    id: str
    author: str
    situation: Dict[str, str]
    value: str
    evidence: List[str]
    confidence: Optional[float]
    how: str
    ts: float

    @property
    def subject(self) -> str:
        return self.situation.get("subject", "")

    @property
    def relation(self) -> str:
        return self.situation.get("relation", "")

    @property
    def context(self) -> Dict[str, str]:
        return {k: v for k, v in self.situation.items()
                if k not in ("subject", "relation")}

    def frame(self) -> Dict[str, str]:
        return {**self.situation, "object": self.value}

    def glyph(self) -> np.ndarray:
        return frame_glyph(self.frame())


@dataclass
class Belief:
    """What the group knows about one question."""
    status: str                 # one of STATUSES
    value: Optional[str]        # best supported object (None if unknown)
    confidence: float           # consensus among qualifying wins
    count: int                  # win precedents that cleared MIN_SIM
    support: float              # mean similarity of those wins
    veto: float                 # nearest refutation of `value`
    outcomes: Dict[str, float]
    receipts: List[Dict[str, Any]]      # wins behind the answer (+author)
    pending: List[str] = field(default_factory=list)  # ungraded claim ids

    @property
    def trusted(self) -> bool:
        return self.status == "known"

    def to_json(self) -> Dict[str, Any]:
        return {"status": self.status, "value": self.value,
                "confidence": round(self.confidence, 4),
                "count": self.count, "support": round(self.support, 4),
                "veto": round(self.veto, 4), "outcomes":
                {k: round(v, 4) for k, v in self.outcomes.items()},
                "receipts": self.receipts, "pending": self.pending}


class KB:
    """The shared knowledge base. One instance per process; any number
    of processes may open the same root concurrently."""

    def __init__(self, root: Optional[str] = None, min_sim: float = MIN_SIM,
                 min_conf: float = MIN_CONF, min_count: int = MIN_COUNT,
                 veto_rule: str = "trusted", min_reliability: float = 0.5):
        """veto_rule: "nearest" (kernel rule 3): an outcome is suppressed
        once its nearest refutation is as close as the wins for it --
        for an exact question ONE refutation suffices. "parity": also
        require at least as many close refutations as close wins, so a
        single noisy or hostile grader cannot erase a reproduced fact
        (but real drift is slow to catch). "trusted" (default):
        "nearest", counting only refutations by graders whose grades
        agree with their peers' (reliability(), graders grade graders)."""
        if veto_rule not in ("nearest", "parity", "trusted"):
            raise ValueError(veto_rule)
        self.veto_rule = veto_rule
        self.min_reliability = min_reliability
        self.root = Path(root) if root else DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self.min_sim, self.min_conf, self.min_count = min_sim, min_conf, min_count
        kw = dict(dim=DIM, seed=SEED, min_sim=min_sim, k=50)
        self.claims = Space(path=str(self.root / "claims.db"), **kw)
        self.wins = Space(path=str(self.root / "wins.db"), **kw)
        self.vetoes = Space(path=str(self.root / "vetoes.db"), **kw)
        self.db = sqlite3.connect(str(self.root / "ledger.db"), timeout=10.0)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS claims (
              id TEXT PRIMARY KEY, author TEXT NOT NULL,
              situation TEXT NOT NULL, value TEXT NOT NULL,
              evidence TEXT NOT NULL DEFAULT '[]', confidence REAL,
              how TEXT NOT NULL DEFAULT '', ts REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS grades (
              claim_id TEXT NOT NULL, grader TEXT NOT NULL,
              ok INTEGER NOT NULL, how TEXT NOT NULL DEFAULT '',
              ts REAL NOT NULL, PRIMARY KEY (claim_id, grader));
            CREATE TABLE IF NOT EXISTS asks (
              ts REAL NOT NULL, asker TEXT NOT NULL,
              situation TEXT NOT NULL, status TEXT NOT NULL,
              value TEXT, confidence REAL, count INTEGER);
        """)
        self.db.commit()

    # ── sync ────────────────────────────────────────────────────────
    def refresh(self) -> int:
        """Pull rows other agents wrote since we opened (WAL)."""
        return (self.claims.refresh() + self.wins.refresh()
                + self.vetoes.refresh())

    def close(self) -> None:
        for s in (self.claims, self.wins, self.vetoes):
            s.close()
        self.db.close()

    def __enter__(self) -> "KB":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── tell ────────────────────────────────────────────────────────
    def tell(self, author: str, subject: str, relation: str, obj: str, *,
             context: Optional[Dict[str, str]] = None,
             evidence: Optional[List[str]] = None,
             confidence: Optional[float] = None, how: str = "",
             cid: Optional[str] = None) -> str:
        """File a claim. It is NOT knowledge until someone else grades
        it. evidence = claim ids it was derived from (premises)."""
        situation = question_frame(subject, relation, context)
        cid = cid or "c-" + uuid.uuid4().hex[:10]
        self.db.execute(
            "INSERT OR IGNORE INTO claims VALUES (?,?,?,?,?,?,?,?)",
            (cid, author, json.dumps(situation, sort_keys=True), str(obj),
             json.dumps(list(evidence or [])), confidence, how, time.time()))
        self.db.commit()
        self.claims.author = author
        self.claims.record(situation, str(obj), rid=cid)
        return cid

    def claim(self, cid: str) -> Claim:
        row = self.db.execute(
            "SELECT id, author, situation, value, evidence, confidence, how,"
            " ts FROM claims WHERE id = ?", (cid,)).fetchone()
        if row is None:
            raise KeyError(cid)
        return Claim(row[0], row[1], json.loads(row[2]), row[3],
                     json.loads(row[4]), row[5], row[6], row[7])

    def all_claims(self, author: Optional[str] = None) -> List[Claim]:
        q = "SELECT id FROM claims" + (" WHERE author = ?" if author else "")
        q += " ORDER BY ts"
        rows = self.db.execute(q, (author,) if author else ()).fetchall()
        return [self.claim(r[0]) for r in rows]

    # ── grade ───────────────────────────────────────────────────────
    def grade(self, grader: str, cid: str, ok: bool, how: str = "") -> str:
        """Grade someone else's claim by trying to reproduce it.
        One grade per (claim, grader); re-grading replaces the ledger
        row but a precedent, once written, stays (kernel: permanent)."""
        c = self.claim(cid)
        if grader == c.author:
            raise SelfGrade(f"{grader} cannot grade its own claim {cid}")
        self.db.execute("INSERT OR REPLACE INTO grades VALUES (?,?,?,?,?)",
                        (cid, grader, int(bool(ok)), how, time.time()))
        self.db.commit()
        space = self.wins if ok else self.vetoes
        rid = f"{cid}~{grader}"
        space.refresh()
        if rid not in set(space._ids):   # kernel record() would append a
            space.author = grader        # duplicate in memory on re-grade
            space.record(c.situation, c.value, rid=rid)
        return "win" if ok else "veto"

    def verify(self, grader: str, cid: str,
               reproduce: Callable[[Claim], Optional[str]],
               how: str = "reproduced") -> Optional[bool]:
        """Grade by reproduction: `reproduce(claim)` returns the value
        the GRADER gets in its own world (None = could not test, no
        grade written). ok = (reproduced value == claimed value)."""
        c = self.claim(cid)
        got = reproduce(c)
        if got is None:
            return None
        ok = str(got) == c.value
        self.grade(grader, cid, ok,
                   how if ok else f"{how}: got {got!r}, claimed {c.value!r}")
        return ok

    def grades(self, cid: str) -> List[Dict[str, Any]]:
        return [{"grader": g, "ok": bool(o), "how": h, "ts": t}
                for g, o, h, t in self.db.execute(
                    "SELECT grader, ok, how, ts FROM grades WHERE claim_id=?"
                    " ORDER BY ts", (cid,))]

    def lineage(self, cid: str) -> List[str]:
        """Every claim `cid` rests on, through evidence= links
        (derived_from is transitive), nearest first."""
        out, todo = [], list(self.claim(cid).evidence)
        while todo:
            e = todo.pop(0)
            if e in out or e == cid:
                continue
            out.append(e)
            try:
                todo.extend(self.claim(e).evidence)
            except KeyError:
                pass
        return out

    def suspects(self) -> List[str]:
        """Claims derived (at any depth) from a premise someone
        refuted: their grounds are gone, they should be re-graded."""
        refuted = {r[0] for r in self.db.execute(
            "SELECT DISTINCT claim_id FROM grades WHERE ok = 0")}
        return [c.id for c in self.all_claims()
                if c.evidence and refuted.intersection(self.lineage(c.id))]

    def reliability(self, min_evidence: int = 5) -> Dict[str, float]:
        """Graders grade graders: for each grader, the fraction of its
        grades that agree with the majority of the OTHER graders of the
        same claim (claims with no other grader are skipped). Fewer than
        `min_evidence` comparable grades -> 1.0 (benefit of the doubt)."""
        key = (min_evidence,) + tuple(self.db.execute(
            "SELECT COUNT(*), MAX(ts) FROM grades").fetchone())
        if getattr(self, "_rel_cache", (None,))[0] == key:
            return self._rel_cache[1]
        rows = self.db.execute(
            "SELECT claim_id, grader, ok FROM grades").fetchall()
        by_claim: Dict[str, Dict[str, int]] = {}
        for cid, g, ok in rows:
            by_claim.setdefault(cid, {})[g] = ok
        agree: Dict[str, List[int]] = {}
        for votes in by_claim.values():
            if len(votes) < 2:
                continue
            for g, ok in votes.items():
                others = [o for h, o in votes.items() if h != g]
                maj = sum(others) * 2
                if maj == len(others):
                    continue                      # peers split: no signal
                agree.setdefault(g, []).append(int(ok == (maj > len(others))))
        rel = {g: (float(np.mean(a)) if len(a) >= min_evidence else 1.0)
               for g, a in agree.items()}
        self._rel_cache = (key, rel)
        return rel

    def pending(self, grader: str, limit: int = 50) -> List[Claim]:
        """Claims by OTHER agents that `grader` has not graded yet --
        the to-do list that turns claims into knowledge."""
        rows = self.db.execute(
            "SELECT id FROM claims WHERE author != ? AND id NOT IN "
            "(SELECT claim_id FROM grades WHERE grader = ?) ORDER BY ts "
            "LIMIT ?", (grader, grader, limit)).fetchall()
        return [self.claim(r[0]) for r in rows]

    # ── ask ─────────────────────────────────────────────────────────
    def ask(self, subject: str, relation: str, *,
            context: Optional[Dict[str, str]] = None,
            asker: str = "anon", log: bool = True) -> Belief:
        return self.ask_situation(question_frame(subject, relation, context),
                                  asker=asker, log=log)

    def ask_situation(self, situation: Dict[str, str], *, asker: str = "anon",
                      log: bool = True) -> Belief:
        self.refresh()
        a = self.wins.query(situation)
        receipts = [r for r in a.to_json()["receipts"]
                    if r["sim"] >= self.min_sim]
        pending = self._pending_for(situation)
        if a.sufficient:
            # Vetoes suppress: an outcome whose nearest refutation sits
            # as close as the wins voting for it loses its vote
            # (matches(), undilutable). The rest vote as usual.
            by_out: Dict[str, List[float]] = {}
            for r in receipts:
                by_out.setdefault(r["outcome"], []).append(r["sim"])
            vetoed = {o: self.vetoes.matches(situation, o) for o in by_out}
            if self.veto_rule == "trusted":
                rel = self.reliability()
                v = self.vetoes.query(situation).to_json()["receipts"]
                vetoed = {o: max([r["sim"] for r in v if r["outcome"] == o
                                  and rel.get(r["author"], 1.0)
                                  >= self.min_reliability] or [0.0])
                          for o in by_out}
            if self.veto_rule == "parity":
                v = self.vetoes.query(situation).to_json()["receipts"]
                nref: Dict[str, int] = {}
                for r in v:
                    if r["sim"] >= self.min_sim:
                        nref[r["outcome"]] = nref.get(r["outcome"], 0) + 1
                alive = {o: s for o, s in by_out.items()
                         if vetoed[o] < float(np.mean(s))
                         or nref.get(o, 0) < len(s)}
            else:
                alive = {o: s for o, s in by_out.items()
                         if vetoed[o] < float(np.mean(s))}
            if not alive:
                b = Belief("vetoed", a.top, a.confidence, a.count, a.support,
                           vetoed[a.top], a.outcomes, receipts, pending)
            else:
                w = {o: float(sum(s)) for o, s in alive.items()}
                total = sum(w.values()) or 1.0
                outcomes = {o: v / total for o, v in w.items()}
                top = max(outcomes, key=outcomes.get)
                sims = [x for s in alive.values() for x in s]
                count, conf = len(sims), outcomes[top]
                if conf < self.min_conf or (conf <= self.min_conf
                                            and len(outcomes) > 1):
                    status = "contested"         # no strict majority
                elif count < self.min_count:
                    status = "uncertain"
                else:
                    status = "known"
                b = Belief(status, top, conf, count, float(np.mean(sims)),
                           vetoed[top], outcomes,
                           [r for r in receipts if r["outcome"] in alive],
                           pending)
        else:
            c = self.claims.query(situation)
            if c.sufficient:
                # no reproduction yet: a claimed value that a (reliable)
                # grader already refuted is reported as vetoed, not claimed
                rel = (self.reliability() if self.veto_rule == "trusted"
                       else {})
                v = self.vetoes.query(situation).to_json()["receipts"]
                alive = {o: w for o, w in c.outcomes.items()
                         if not any(r["outcome"] == o and r["sim"] >= c.support
                                    and rel.get(r["author"], 1.0)
                                    >= self.min_reliability for r in v)}
                if alive:
                    top = max(alive, key=alive.get)
                    b = Belief("claimed", top, 0.0, 0, c.support, 0.0,
                               c.outcomes, [], pending)
                else:
                    b = Belief("vetoed", c.top, 0.0, 0, c.support,
                               self.vetoes.matches(situation, c.top),
                               c.outcomes, [], pending)
            else:
                b = Belief("unknown", None, 0.0, 0, 0.0, 0.0, {}, [], pending)
        if log:
            self.db.execute("INSERT INTO asks VALUES (?,?,?,?,?,?,?)",
                            (time.time(), asker,
                             json.dumps(situation, sort_keys=True), b.status,
                             b.value, b.confidence, b.count))
            self.db.commit()
        return b

    def ask_glyph(self, question: np.ndarray, *, asker: str = "anon",
                  log: bool = True) -> Belief:
        """Answer a question that arrives as a glyph (e.g. a courier
        message's content). Decoded with lexicon's language; an
        'object' role (if the asker put a '?' there) is dropped."""
        from language import LX  # type: ignore
        meaning = LX.decode(question)
        if not isinstance(meaning, dict):
            raise ValueError(f"question glyph did not decode to a frame: "
                             f"{meaning!r}")
        envelope = {"object", "act", "want", "from", "to", "topic",
                    "reply_to", "thread", "proto"}
        situation = {k: str(v) for k, v in meaning.items()
                     if k not in envelope and v != "?"
                     and isinstance(v, (str, int, float))}
        return self.ask_situation(situation, asker=asker, log=log)

    def _pending_for(self, situation: Dict[str, str]) -> List[str]:
        key = json.dumps(situation, sort_keys=True)
        rows = self.db.execute(
            "SELECT id FROM claims WHERE situation = ? AND id NOT IN "
            "(SELECT claim_id FROM grades)", (key,)).fetchall()
        return [r[0] for r in rows]

    def feedback(self, user: str, belief: Belief, ok: bool,
                 how: str = "used it; the world said") -> int:
        """The world grades an ANSWER after someone acted on it: the
        user grades every claim behind the belief's receipts that it did
        not author itself. This is how a reflex that went stale after
        drift gets vetoed. Returns how many claims were graded."""
        cids = {r["id"].partition("~")[0] for r in belief.receipts}
        n = 0
        for cid in sorted(cids):
            try:
                c = self.claim(cid)
            except KeyError:
                continue
            if c.author != user and c.value == belief.value:
                self.grade(user, cid, ok, how)
                n += 1
        return n

    # ── the kernel decision loop, wrapped ───────────────────────────
    def decide(self, asker: str, subject: str, relation: str,
               consult: Callable[[], str], *,
               context: Optional[Dict[str, str]] = None,
               how: str = "consulted") -> Dict[str, Any]:
        """Reflex when the group KNOWS; otherwise consult (paid) and
        file the consulted answer as a claim for others to grade."""
        b = self.ask(subject, relation, context=context, asker=asker)
        if b.status == "known":
            return {"value": b.value, "mode": "reflex", "belief": b,
                    "claim": None}
        value = str(consult())
        cid = self.tell(asker, subject, relation, value, context=context,
                        how=how)
        return {"value": value, "mode": "consult", "belief": b, "claim": cid}

    # ── knowledge as a glyph ────────────────────────────────────────
    def concept(self, subject: str, status: str = "known") -> Optional[np.ndarray]:
        """Everything the group knows (default: trusted facts only)
        about `subject`, as ONE glyph: the bundle of its fact frames.
        Probe it with bind(glyph, role('relation')) etc."""
        glyphs = []
        for c in self.all_claims():
            if c.subject != str(subject):
                continue
            b = self.ask_situation(c.situation, log=False)
            if (status == "any" or b.status == status) and b.value == c.value:
                glyphs.append(c.glyph())
        uniq = {g.tobytes(): g for g in glyphs}
        return bundle(list(uniq.values())) if uniq else None

    # ── integrity & learning curve ──────────────────────────────────
    def audit(self) -> Dict[str, Any]:
        """Replay the receipts: every win/veto precedent must match a
        ledger grade by a grader who is not the claim's author."""
        bad, superseded = [], []
        for space, ok in ((self.wins, 1), (self.vetoes, 0)):
            for rid, author in zip(space._ids, space._authors):
                cid, _, grader = rid.partition("~")
                row = self.db.execute(
                    "SELECT g.ok, c.author FROM grades g JOIN claims c ON "
                    "c.id = g.claim_id WHERE g.claim_id=? AND g.grader=?",
                    (cid, grader)).fetchone()
                if row is None or grader != author or row[1] == grader:
                    bad.append(rid)
                elif row[0] != ok:
                    superseded.append(rid)   # grader later changed its mind
        return {"wins": len(self.wins), "vetoes": len(self.vetoes),
                "claims": len(self.claims), "bad_receipts": bad,
                "superseded": superseded}

    def stats(self) -> Dict[str, Any]:
        self.refresh()
        by_author = dict(self.db.execute(
            "SELECT author, COUNT(*) FROM claims GROUP BY author"))
        by_grader = dict(self.db.execute(
            "SELECT grader, COUNT(*) FROM grades GROUP BY grader"))
        return {"claims": len(self.claims), "wins": len(self.wins),
                "vetoes": len(self.vetoes), "claims_by_author": by_author,
                "grades_by_grader": by_grader}

    def curve(self, window: int = 20) -> List[Dict[str, Any]]:
        """The product metric from real use: per window of asks, the
        fraction answered 'known' (reflex) vs needing a consult."""
        rows = self.db.execute(
            "SELECT status FROM asks ORDER BY ts").fetchall()
        out = []
        for i in range(0, len(rows), window):
            chunk = [r[0] for r in rows[i:i + window]]
            out.append({"asks": f"{i + 1}-{i + len(chunk)}",
                        "known_rate": round(chunk.count("known") / len(chunk), 3),
                        "unknown_rate": round(chunk.count("unknown") / len(chunk), 3)})
        return out
