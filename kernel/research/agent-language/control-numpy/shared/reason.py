"""reason.py: thinking in the language (owner: reasoner).

Built on shared/language.py (lexicon). Operations that produce NEW knowledge
from representations; every one returns a calibrated Answer that may be
"unknown" (the lexicon atom for abstention).

    R = Reasoner()                              # default lexicon; Reasoner(lex=Lexicon(path=None)) in tests
    R.query(vec, "obj")                         # ask one slot of a meaning (path allowed: "because", "#0")
    R.analogy(rec_a, rec_b, "dollar")           # what in B plays the part "dollar" plays in A
    R.abstract([v1, v2, ...])                   # the gist: roles constant across cases
    fm = FactMemory(R); fm.add("cat","is_a","mammal")
    fm.ask("cat", "is_a")                       # (s r ?) by vector match + unbind
    fm.infer(DEFAULT_RULES)                     # chained Horn-rule inference to a fixpoint
    R.analogy_facts(fm, "paris","france","rome")  # A:B :: C:?
    R.explain(fm, conclusion_vec)               # decode the nested BECAUSE tree from the vector
    fm.answer({"act":"ask","subj":"cat","rel":"has","obj":"?"})  # question meaning -> answer meaning

A derived fact is itself a meaning:
    {act: assert, subj, rel, obj, rule: <rule name>, conf: conf_hi|mid|lo,
     because: [<premise vector>, <premise vector>]}
Each premise is embedded as its plain (assert s r o) vector (weight 1, the
same vector knowledge.py stores), so ANY agent holding the KB can read a
conclusion's premises by cleanup; a premise that is itself a conclusion is
explained in turn (explain() recurses), so proofs nest to any depth.

Confidence: a cleanup's gap = (top1 - top2) similarity in noise units
(sim * sqrt(D); a random pair is ~N(0,1)). A Calibrator fit by pool-adjacent-
violators on held-out synthetic queries (shared/reason_calibration.json)
maps gap -> P(correct). Below tau the answer is "unknown".

Grading: every derived fact told to the KB carries
    check = "reason:<rule>:<premise fid>,<premise fid>"
Anyone can rerun it: kb.reproduce(agent, fid) calls recheck_kb (registered
with knowledge.register_checker on import of this module).
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import language as L  # noqa: E402

CALIB_FILE = HERE / "reason_calibration.json"
UNKNOWN = "unknown"
Z_FLOOR = 5.0          # sigma; P(noise > 5 sigma) ~ 3e-7 per candidate
D = L.D
SQRT_D = math.sqrt(D)


# ---------------------------------------------------------------- primitives

def filler_key(name: str) -> np.ndarray:
    """What a word looks like once stored in a slot (grammar rolls fillers by 1)."""
    return np.roll(L.atom(name), 1)


class Codebook:
    """Names -> vectors, for vectorised cleanup (words, roles or fact vectors)."""

    def __init__(self, names: Iterable[str] = (), kind: str = "word"):
        self.kind = kind
        self.names: List[str] = []
        self._idx: Dict[str, int] = {}
        self._rows: List[np.ndarray] = []
        self._M: Optional[np.ndarray] = None
        for n in names:
            self.add(n)

    def add(self, name: str, vec: Optional[np.ndarray] = None):
        if name in self._idx:
            if vec is not None:
                self._rows[self._idx[name]] = np.asarray(vec, np.int8)
                self._M = None
            return
        if vec is None:
            vec = L.role(name) if self.kind == "role" else L.atom(name)
        self._idx[name] = len(self.names)
        self.names.append(name)
        self._rows.append(np.asarray(vec, np.int8))
        self._M = None

    def __len__(self):
        return len(self.names)

    def __contains__(self, n):
        return n in self._idx

    def vec(self, name) -> np.ndarray:
        return self._rows[self._idx[name]]

    @property
    def M(self) -> np.ndarray:
        if self._M is None:
            self._M = np.stack(self._rows).astype(np.float32) if self._rows \
                else np.zeros((0, D), np.float32)
        return self._M

    def z(self, v: np.ndarray) -> np.ndarray:
        """Similarity of v to every row, in noise units (random ~ N(0,1))."""
        v = np.asarray(v, np.float32)
        return self.M @ v / (np.linalg.norm(v) + 1e-12)

    def top(self, v: np.ndarray, k: int = 2) -> List[Tuple[str, float]]:
        s = self.z(v)
        idx = np.argsort(-s)[:k]
        return [(self.names[i], float(s[i])) for i in idx]


# ---------------------------------------------------------------- calibration

class Calibrator:
    """Monotone map gap (noise units) -> P(top-1 correct), fit by PAV."""

    def __init__(self, xs=None, ps=None):
        # untrained prior: a gap under 3 sigma is noise, over 7 is reliable
        self.xs = np.asarray(xs if xs is not None else [0.0, 3.0, 5.0, 7.0, 12.0])
        self.ps = np.asarray(ps if ps is not None else [0.0, 0.05, 0.5, 0.95, 0.99])

    @staticmethod
    def fit(scores: Sequence[float], correct: Sequence[bool], bins: int = 40) -> "Calibrator":
        s = np.asarray(scores, float)
        c = np.asarray(correct, float)
        o = np.argsort(s)
        s, c = s[o], c[o]
        chunks = [ch for ch in np.array_split(np.arange(len(s)), bins) if len(ch)]
        blocks = [[float(s[ch].mean()), float(c[ch].sum()), float(len(ch))] for ch in chunks]
        i = 0
        while i < len(blocks) - 1:          # pool adjacent violators
            a, b = blocks[i], blocks[i + 1]
            if a[1] / a[2] > b[1] / b[2]:
                w = a[2] + b[2]
                blocks[i] = [(a[0] * a[2] + b[0] * b[2]) / w, a[1] + b[1], w]
                del blocks[i + 1]
                i = max(i - 1, 0)
            else:
                i += 1
        xs = [b[0] for b in blocks]
        ps = [(b[1] + 0.5) / (b[2] + 1.0) for b in blocks]   # Laplace: never 0 or 1
        return Calibrator(xs, ps)

    # An absolute floor: whatever the gap, a top-1 below Z_FLOOR sigma is not
    # evidence of anything (small codebooks make large gaps out of pure noise).
    # Reads under the floor get the measured accuracy of that region, p_low.
    z_floor = Z_FLOOR
    p_low = 0.0

    def __call__(self, gap: float) -> float:
        return float(np.interp(gap, self.xs, self.ps))

    def p(self, z1: float, gap: float) -> float:
        return self(gap) if z1 >= self.z_floor else min(self(gap), self.p_low)

    def to_json(self):
        return {"xs": [float(x) for x in self.xs], "ps": [float(p) for p in self.ps],
                "z_floor": self.z_floor, "p_low": self.p_low}

    @staticmethod
    def load(path: Path = CALIB_FILE) -> Optional["Calibrator"]:
        if path.exists():
            d = json.loads(path.read_text())
            c = Calibrator(d["xs"], d["ps"])
            c.z_floor = d.get("z_floor", Z_FLOOR)
            c.p_low = d.get("p_low", 0.0)
            return c
        return None


def ece(probs: Sequence[float], correct: Sequence[bool], bins: int = 10) -> float:
    """Expected calibration error: |mean confidence - accuracy| averaged over bins."""
    p = np.asarray(probs, float)
    c = np.asarray(correct, float)
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum((b == k).mean() * abs(p[b == k].mean() - c[b == k].mean())
                     for k in range(bins) if (b == k).any()))


# ---------------------------------------------------------------- answers

@dataclass
class Answer:
    value: str                    # the answer, or "unknown"
    conf: float                   # calibrated P(correct)
    guess: str = ""               # best candidate even when abstaining
    z: float = 0.0                # top similarity in noise units
    gap: float = 0.0              # top1 - top2 in noise units
    why: list = field(default_factory=list)

    @property
    def known(self) -> bool:
        return self.value != UNKNOWN

    def conf_atom(self) -> str:
        return conf_atom(self.conf)


def conf_atom(p: float) -> str:
    return "conf_hi" if p >= 0.9 else "conf_mid" if p >= 0.6 else "conf_lo"


class Reasoner:
    def __init__(self, lex: Optional[L.Lexicon] = None, tau: float = 0.8,
                 calibrator: Optional[Calibrator] = None):
        self.lex = lex if lex is not None else L.default_lexicon()
        self.persist = self.lex.path is not None
        self.tau = tau
        self.cal = calibrator or Calibrator.load() or Calibrator()
        self._rb = Codebook(kind="role")

    def encode(self, m) -> np.ndarray:
        return L.encode(m, self.lex, persist=self.persist)

    @property
    def roles(self) -> Codebook:
        """Every non-positional role the lexicon knows (grows with it)."""
        known = [r for r in self.lex.roles if not r.startswith("#")]
        for r in known[len(self._rb):]:
            self._rb.add(r)
        return self._rb

    def words(self) -> Codebook:
        """Every word the lexicon knows (cached; grows as the lexicon learns)."""
        wb = getattr(self, "_wb", None)
        if wb is None:
            wb = self._wb = Codebook()
        for w in self.lex.words[len(wb):]:
            wb.add(w)
        return wb

    # -- cleanup with calibrated abstention
    def cleanup(self, v: np.ndarray, book: Codebook, why=None) -> Answer:
        if len(book) == 0:
            return Answer(UNKNOWN, 0.0, why=why or [])
        top = book.top(v, 2)
        z1 = top[0][1]
        z2 = top[1][1] if len(top) > 1 else 0.0
        gap = z1 - max(z2, 0.0)
        p = self.cal.p(z1, gap)
        return Answer(top[0][0] if p >= self.tau else UNKNOWN, p, top[0][0], z1, gap, why or [])

    # -- 1. structured question: read one slot (or a path of slots) of a meaning
    def query(self, vec: np.ndarray, *path: str, book: Optional[Codebook] = None) -> Answer:
        u = L.unbind_role(vec, *path)
        return self.cleanup(u, book if book is not None else self.words(), why=[("query",) + path])

    # -- 2a. analogy between records: what in B plays the part x plays in A?
    def role_of(self, rec: np.ndarray, x: str) -> Answer:
        """Which role holds x?  rec * roll(x) ~ role(r)."""
        return self.cleanup(L.bind(rec, filler_key(x)), self.roles, why=[("role_of", x)])

    def analogy(self, rec_a: np.ndarray, rec_b: np.ndarray, x: str,
                book: Optional[Codebook] = None) -> Answer:
        r = self.role_of(rec_a, x)
        if not r.known:
            return Answer(UNKNOWN, r.conf, r.guess, r.z, r.gap, [("analogy", x, "role unknown")])
        a = self.query(rec_b, r.value, book=book)
        p = a.conf * r.conf
        return Answer(a.guess if p >= self.tau else UNKNOWN, p, a.guess, a.z, a.gap,
                      [("analogy", x, "is the", r.value, "of A; the", r.value, "of B is", a.guess)])

    def analogy_mapping(self, rec_a, rec_b, x: str, book: Optional[Codebook] = None) -> Answer:
        """Kanerva one-shot, no role search: roll^-1((A*B) * roll(x)) ~ B's filler of x's role.
        Both frames carry the FRAME marker, so A*B also contains the identity
        map (x -> x); x itself is therefore excluded from the candidates."""
        u = np.roll(L.bind(L.bind(rec_a, rec_b), filler_key(x)), -1)
        base = book if book is not None else self.words()
        cand = Codebook([n for n in base.names if n != x])
        return self.cleanup(u, cand, why=[("mapping", x)])

    # -- 3. abstraction: the gist of many cases
    def abstract(self, cases: Sequence[np.ndarray], roles: Optional[Sequence[str]] = None,
                 book: Optional[Codebook] = None, min_support: float = 0.5):
        """The gist of many cases.
        1. prototype = majority bundle of the cases (one vector, a new meaning);
        2. per role, the prototype proposes a candidate filler (unbind+cleanup);
        3. support = fraction of the cases whose own slot reads back as that
           candidate. A role is in the gist iff support > min_support (a strict majority) and the
           prototype read is confident; otherwise it varies ('unknown').
        Returned Answers carry conf = support, why = [("support", k, n)]."""
        cases = list(cases)
        proto = L.bundle(cases)
        book = book if book is not None else self.words()
        C = np.stack(cases)
        gist, varying = {}, {}
        for r in (roles or self.roles.names):
            a = self.query(proto, r, book=book)
            if a.guess:
                key = np.roll(L.bind(np.roll(L.atom(a.guess), 1), L.role(r)), 0).astype(np.float32)
                # does case i hold (r: guess)?  slot similarity in noise units, > 6 sigma
                zs = C.astype(np.float32) @ key / SQRT_D
                k = int((zs > 6.0).sum())
            else:
                k = 0
            sup = k / len(cases)
            ok = a.conf >= self.tau and sup > min_support
            ans = Answer(a.guess if ok else UNKNOWN, sup, a.guess, a.z, a.gap,
                         [("support", k, len(cases))])
            (gist if ok else varying)[r] = ans
        return proto, gist, varying

    def classify(self, v: np.ndarray, prototypes: Dict[str, np.ndarray]) -> Answer:
        book = Codebook(kind="proto")
        for n, p in prototypes.items():
            book.add(n, p)
        return self.cleanup(v, book, why=[("classify",)])

    # -- 2b. relational analogy over facts: A:B :: C:?
    def analogy_facts(self, fm: "FactMemory", a: str, b: str, c: str) -> Answer:
        """a:b :: c:?  Find a relation a->b, apply it to c. Known iff both
        facts are known (each read >= tau, each fact >= fm.min_trust);
        conf = product of the two (reported, e.g. conf_lo for two 0.66 facts)."""
        best = Answer(UNKNOWN, 0.0, why=[("analogy", a, b, "no relation found")])
        for rel, p_rel, ok_rel in fm.relations_between(a, b):
            ans = fm.ask(c, rel)
            p = p_rel * ans.conf
            known = ok_rel and ans.known
            if (known, p) > (best.known, best.conf):
                best = Answer(ans.guess if known else UNKNOWN, p, ans.guess, ans.z, ans.gap,
                              [("because", a, rel, b), ("and", c, rel, ans.guess)])
        return best

    # -- 4b. explanation: decode the derivation tree out of a conclusion vector
    def explain(self, fm: "FactMemory", v: np.ndarray, depth: int = 4) -> dict:
        s, r, o = (self.query(v, k, book=fm.names).value for k in ("subj", "rel", "obj"))
        node = {"fact": (s, r, o)}
        rule = self.query(v, "rule", book=fm.rule_names)
        if depth > 0 and rule.known:
            node["rule"] = rule.value
            kids = []
            arity = len(fm.rules[rule.value].body) if rule.value in fm.rules else L.MAX_POS
            for i in range(arity):
                hit = self.cleanup(L.unbind_role(v, "because", f"#{i}"), fm.plain_book)
                if not hit.known:
                    break
                kids.append(self.explain(fm, fm.facts_book.vec(hit.value), depth - 1))
            node["because"] = kids
        return node


# ---------------------------------------------------------------- facts + inference

@dataclass
class Fact:
    fid: str
    s: str
    r: str
    o: str
    conf: float = 1.0
    rule: Optional[str] = None
    premises: Tuple[str, ...] = ()
    depth: int = 0


def fact_id(s, r, o) -> str:
    """Same id scheme as shared/knowledge.py, so fids agree across agents."""
    import hashlib
    return hashlib.sha256(f"{s}\x1f{r}\x1f{o}".encode()).hexdigest()[:12]


def fact_meaning(s, r, o) -> dict:
    return {"act": "assert", "subj": s, "rel": r, "obj": o}


FUNCTIONAL = ("owner", "capital_of", "equals", "bytes")


class FactMemory:
    """Triples as language vectors. Questions are answered by vector match
    (every given slot must be present) and read back by unbind + cleanup."""

    SLOT = {"s": "subj", "r": "rel", "o": "obj"}

    def __init__(self, R: Reasoner, min_trust: Optional[float] = None):
        """min_trust: how true a fact must be to answer from it (the group's
        KB uses 0.6). Separate from R.tau, which is how sure the vector READ
        must be. Default: R.tau."""
        self.R = R
        self.min_trust = R.tau if min_trust is None else min_trust
        self.facts: Dict[str, Fact] = {}
        self.names = Codebook([UNKNOWN])      # every atom that appears in a fact
        self.rule_names = Codebook([UNKNOWN])
        self.rules: Dict[str, "Rule"] = dict(RULES_BY_NAME)
        self.inf_cal: Optional[Calibrator] = None   # learned from grades of conclusions
        self.facts_book = Codebook(kind="fact")   # fid -> full vector (with rule, conf, because)
        self.plain_book = Codebook(kind="fact")   # fid -> (assert s r o) vector = the KB's vector

    def add(self, s, r, o, conf=1.0, rule=None, premises=(), depth=0) -> Fact:
        fid = fact_id(s, r, o)
        if fid in self.facts:
            f = self.facts[fid]
            f.conf = max(f.conf, conf)
            return f
        f = Fact(fid, s, r, o, conf, rule, tuple(premises), depth)
        m = fact_meaning(s, r, o)
        if rule:
            m.update(rule=rule, conf=conf_atom(conf),
                     because=[self.plain_book.vec(p) for p in premises])
            self.rule_names.add(rule)
        self.facts[fid] = f
        for n in (s, r, o):
            self.names.add(n)
        self.facts_book.add(fid, self.R.encode(m))
        self.plain_book.add(fid, self.R.encode(fact_meaning(s, r, o)) if rule else self.facts_book.vec(fid))
        return f

    def vec(self, fid) -> np.ndarray:
        return self.facts_book.vec(fid)

    def conf(self, f: Fact) -> float:
        """Confidence of a fact. Told facts: their trust. Conclusions: the
        raw product of premise trust, re-mapped by what grading has taught
        us about conclusions of that raw confidence (if we have been graded)."""
        if f.rule and self.inf_cal is not None:
            return self.inf_cal(f.conf)
        return f.conf

    def learn_from_grades(self, graded: Sequence[Tuple[str, bool]], bins: int = 10) -> Calibrator:
        """graded = [(fid of a conclusion, was it right?)], e.g. from the KB's
        outside grades. Fits raw-conf -> P(right) by PAV. The more we are
        graded, the better our 'I don't know' gets."""
        xs = [self.facts[fid].conf for fid, _ in graded if fid in self.facts]
        ys = [ok for fid, ok in graded if fid in self.facts]
        self.inf_cal = Calibrator.fit(xs, ys, bins=bins)
        return self.inf_cal

    def match(self, s=None, r=None, o=None, min_z: float = 8.0) -> List[Tuple[Fact, float]]:
        """Facts that hold every given slot. Score = weakest slot in noise units
        (a random slot ~N(0,1); a present slot of a 4-7 leaf fact scores 20-35)."""
        keys = [L.bind(L.role(self.SLOT[k]), filler_key(x))
                for k, x in (("s", s), ("r", r), ("o", o)) if x is not None]
        if not keys or not len(self.facts_book):
            return []
        P = np.stack(keys).astype(np.float32)
        z = (self.facts_book.M @ P.T).min(axis=1) / SQRT_D
        hits = np.nonzero(z >= min_z)[0]
        out = [(self.facts[self.facts_book.names[i]], float(z[i])) for i in hits]
        return sorted(out, key=lambda t: -t[1])

    def ask(self, s: str, r: str) -> Answer:
        """(s r ?): vector match picks the fact(s); OBJ is read back out of the
        fact vector by unbinding + cleanup. conf = readback conf * fact conf."""
        hits = self.match(s=s, r=r)
        if not hits:
            return Answer(UNKNOWN, 0.0, why=[("no fact matches", s, r)])
        best = None
        for f, _ in hits:
            a = self.R.query(self.vec(f.fid), "obj", book=self.names)
            fc = self.conf(f)
            ok = a.known and fc >= self.min_trust
            a.conf *= fc
            a.why = [("fact", f.fid, f.rule or "told")]
            if best is None or (ok, a.conf) > (best.known, best.conf):
                best = a
                best.value = best.guess if ok else UNKNOWN
        if len(hits) > 1:
            best.why.append(("also", sorted(h[0].o for h in hits if h[0].o != best.guess)))
        return best

    def ask_all(self, s=None, r=None, o=None) -> List[Fact]:
        return [f for f, _ in self.match(s, r, o) if self.conf(f) >= self.min_trust]

    def relations_between(self, a: str, b: str) -> List[Tuple[str, float, bool]]:
        """[(rel, conf, known)] for every fact (a rel b)."""
        out = []
        for f, _ in self.match(s=a, o=b):
            ans = self.R.query(self.vec(f.fid), "rel", book=self.names)
            if ans.known:
                fc = self.conf(f)
                out.append((ans.value, ans.conf * fc, fc >= self.min_trust))
        return out

    # -- entity profiles and their gist (abstraction over the fact memory)
    def profile(self, e: str) -> Optional[np.ndarray]:
        """Everything known about e as one frame-like vector:
        sign(FRAME + sum over (e r o) of role(r) * roll(o))."""
        fs = [f for f, _ in self.match(s=e) if self.conf(f) >= self.min_trust]
        if not fs:
            return None
        acc = L.atom(L.FRAME).astype(np.int32)
        for f in fs:
            acc = acc + (L.role(f.r) * filler_key(f.o)).astype(np.int32)
        return np.where(acc > 0, 1, np.where(acc < 0, -1, L.atom(L.TIE))).astype(np.int8)

    def gist(self, entities: Sequence[str], min_support: float = 0.5):
        """What do these entities have in common?  Prototype = bundle of their
        profiles; every (rel, obj) readable in the prototype is scored by
        support = fraction of profiles that hold it (> 6 sigma)."""
        profs = [(e, self.profile(e)) for e in entities]
        profs = [(e, p) for e, p in profs if p is not None]
        if not profs:
            return None, []
        proto = L.bundle([p for _, p in profs])
        P = np.stack([p for _, p in profs]).astype(np.float32)
        cands = {(f.r, f.o) for e, _ in profs for f, _ in self.match(s=e)}
        out = []
        for r, o in sorted(cands):
            key = (L.role(r) * filler_key(o)).astype(np.float32)
            zp = float(proto.astype(np.float32) @ key / SQRT_D)
            sup = float(((P @ key / SQRT_D) > 6.0).mean())
            if sup > min_support and zp > Z_FLOOR:
                out.append((r, o, sup))
        return proto, sorted(out, key=lambda t: -t[2])

    def premise(self, fid: str) -> dict:
        f = self.facts[fid]
        return fact_meaning(f.s, f.r, f.o)

    def answer(self, q: dict) -> dict:
        """A question MEANING -> an answer MEANING (both in the language).
        Forms (see LANGUAGE.md, Reasoning):
          (query :subj s :rel r :obj ?)              lookup + inferred facts
          (query :subj ? :rel r :obj o)              every s with (s r o)
          (query :subj s :rel r :obj o)              yes / unknown
          (query :rel analogy :subj [a b c] :obj ?)  a:b :: c:?
          (query :rel gist :subj [x y ...] :obj ?)   what x, y, ... share
        Unanswerable -> obj/val = unknown, conf_lo."""
        s, r, o = q.get("subj"), q.get("rel"), q.get("obj")
        if r == "analogy" and isinstance(s, list) and len(s) == 3:
            a = self.R.analogy_facts(self, *s)
            out = {"act": "answer", "rel": "analogy", "subj": list(s), "obj": a.value,
                   "conf": a.conf_atom()}
            prem = [fact_id(*w[1:]) for w in a.why if len(w) == 4]
            if a.known and all(p in self.facts for p in prem):
                out["because"] = [self.premise(p) for p in prem]
            return out
        if r == "gist" and isinstance(s, list):
            _, common = self.gist(s)
            return {"act": "answer", "rel": "gist", "subj": list(s),
                    "obj": [{"rel": rr, "obj": oo} for rr, oo, _ in common][:L.MAX_POS] or UNKNOWN,
                    "conf": "conf_hi" if common else "conf_lo"}
        if o == "?":
            a = self.ask(s, r)
            out = {"act": "answer", "subj": s, "rel": r, "obj": a.value, "conf": a.conf_atom()}
            many = sorted({f.o for f in self.ask_all(s=s, r=r)})
            if a.known and len(many) > 1:          # a multi-valued relation: say all of it
                out["obj"] = many[:L.MAX_POS]
                return out
            fid = a.why[0][1] if a.known and a.why and a.why[0][0] == "fact" else None
            if fid and self.facts[fid].rule:
                f = self.facts[fid]
                out["rule"] = f.rule
                out["because"] = [self.premise(p) for p in f.premises]
            return out
        if s == "?":
            hits = self.ask_all(r=r, o=o)
            return {"act": "answer", "subj": sorted(f.s for f in hits)[:L.MAX_POS] or UNKNOWN,
                    "rel": r, "obj": o, "conf": "conf_hi" if hits else "conf_lo"}
        f = self.facts.get(fact_id(s, r, o))
        known = f is not None and self.conf(f) >= self.min_trust
        return {"act": "answer", "subj": s, "rel": r, "obj": o,
                "conf": conf_atom(self.conf(f)) if f else "conf_lo",
                "val": "yes" if known else UNKNOWN}

    # chained inference: rules are Horn clauses over triple patterns
    def match_many(self, patterns, min_z: float = 8.0, only=None, chunk: int = 256):
        """Batched match(): one matrix product for many (s, r, o) patterns
        (None = free slot). only = optional boolean mask over facts."""
        M = self.facts_book.M
        out = []
        for c0 in range(0, len(patterns), chunk):
            keys, owners = [], []
            for pat in patterns[c0:c0 + chunk]:
                idx = []
                for k, x in zip("sro", pat):
                    if x is not None:
                        keys.append(L.bind(L.role(self.SLOT[k]), filler_key(x)))
                        idx.append(len(keys) - 1)
                owners.append(idx)
            Z = M @ np.stack(keys).astype(np.float32).T / SQRT_D if keys else None
            for idx in owners:
                z = Z[:, idx].min(axis=1)
                ok = z >= min_z
                if only is not None:
                    ok &= only
                out.append([self.facts[self.facts_book.names[i]] for i in np.nonzero(ok)[0]])
        return out

    def infer(self, rules: Sequence["Rule"], max_depth: int = 8, decay: float = 0.98,
              min_conf: float = 0.5) -> List[Fact]:
        """Forward chaining to a fixpoint, semi-naive: after the first round a
        rule only fires on bindings that use at least one fact derived in the
        previous round. Each round may use earlier conclusions as premises, so
        conclusions nest (depth = proof height).
        conf = prod(premise conf) * rule reliability * decay."""
        new: List[Fact] = []
        delta = None                      # None = every fact is new (first round)
        self.rules.update({r.name: r for r in rules})
        for _ in range(max_depth):
            added = {}
            for rule in rules:
                positions = [None] if delta is None else range(len(rule.body))
                for pos in positions:
                    for binding, prem in self._join(rule.body, pos, delta):
                        s, r, o = (binding.get(t, t) for t in rule.head)
                        if s == o and rule.irreflexive:
                            continue
                        fid = fact_id(s, r, o)
                        if fid in self.facts:
                            continue
                        conf = float(np.prod([p.conf for p in prem])) * rule.reliability * decay
                        if conf < min_conf or (fid in added and added[fid][3] >= conf):
                            continue            # keep the strongest proof found this round
                        added[fid] = (s, r, o, conf, rule.name, tuple(p.fid for p in prem),
                                      1 + max(p.depth for p in prem))
            if not added:
                break
            for a in added.values():
                new.append(self.add(*a[:3], conf=a[3], rule=a[4], premises=a[5], depth=a[6]))
            names = self.facts_book.names
            delta = np.array([n in added for n in names])
        return new

    def _join(self, body, restrict_pos, delta):
        """Breadth-first join of the rule body; premise restrict_pos must come
        from delta (mask over facts)."""
        states = [({}, [])]
        for i, pat in enumerate(body):
            pats = [tuple(None if b.get(t, t).startswith("?") else b.get(t, t) for t in pat)
                    for b, _ in states]
            uniq = sorted(set(pats), key=str)
            hits = dict(zip(uniq, self.match_many(uniq, only=delta if i == restrict_pos else None)))
            nxt = []
            for (b, prem), q in zip(states, pats):
                for f in hits[q]:
                    nb = dict(b)
                    ok = True
                    for t, val in zip(pat, (f.s, f.r, f.o)):
                        want = nb.get(t, t)          # bound variable or constant
                        if want.startswith("?"):
                            nb[t] = val              # first binding of a variable
                        elif want != val:
                            ok = False
                            break
                    if ok and all(f.fid != p.fid for p in prem):
                        nxt.append((nb, prem + [f]))
            states = nxt
            if not states:
                break
        return states

    def contradictions(self, functional: Sequence[str] = FUNCTIONAL) -> List[Tuple[Fact, Fact]]:
        """For a functional relation (one object per subject: owner, capital_of,
        equals, bytes, ...), two different objects for the same subject cannot
        both be true. Returns (stronger, weaker) pairs, found by vector match."""
        out = []
        for r in functional:
            by_s: Dict[str, List[Fact]] = {}
            for f, _ in self.match(r=r):
                by_s.setdefault(f.s, []).append(f)
            for fs in by_s.values():
                if len({f.o for f in fs}) > 1:
                    fs = sorted(fs, key=lambda f: -self.conf(f))
                    out += [(fs[0], w) for w in fs[1:] if w.o != fs[0].o]
        return out

    # KB bridge
    def load_kb(self, kb, min_trust: float = 0.0) -> int:
        n = 0
        for fid, s, r, o, t in kb.facts(min_trust=min_trust):
            self.add(s, r, o, conf=t)
            n += 1
        return n

    def tell_kb(self, kb, facts: Sequence[Fact], agent: str = "reasoner") -> List[str]:
        out = []
        for f in facts:
            chk = f"reason:{f.rule}:{','.join(f.premises)}" if f.rule else None
            out.append(kb.tell(agent, f.s, f.r, f.o, check=chk,
                               trail=list(f.premises) if f.rule else None))
        return out


@dataclass
class Rule:
    name: str
    body: Tuple[Tuple[str, str, str], ...]
    head: Tuple[str, str, str]
    reliability: float = 1.0
    irreflexive: bool = False

    def meaning(self) -> dict:
        """A rule is itself a meaning: (rule :name .. :cond [..] :then (..))."""
        pat = lambda p: {"subj": p[0], "rel": p[1], "obj": p[2]}
        return {"act": "rule", "name": self.name, "cond": [pat(p) for p in self.body],
                "then": pat(self.head)}


def transitive(rel, reliability=1.0):
    return Rule(f"transitive_{rel}", (("?x", rel, "?y"), ("?y", rel, "?z")),
                ("?x", rel, "?z"), reliability, True)


def inherit(rel, via="is_a", reliability=0.95):
    return Rule(f"inherit_{rel}", (("?x", via, "?y"), ("?y", rel, "?z")),
                ("?x", rel, "?z"), reliability)


def inverse(rel, inv, reliability=1.0):
    return Rule(f"inverse_{rel}", (("?x", rel, "?y"),), ("?y", inv, "?x"), reliability)


def compose(r1, r2, out, reliability=0.95):
    return Rule(f"compose_{r1}_{r2}", (("?x", r1, "?y"), ("?y", r2, "?z")),
                ("?x", out, "?z"), reliability)


DEFAULT_RULES = [transitive("is_a"), transitive("part_of"), transitive("located_in"),
                 transitive("depends_on"),
                 inherit("has"), inherit("can"), inverse("parent_of", "child_of"),
                 compose("parent_of", "parent_of", "grandparent_of"),
                 compose("capital_of", "located_in", "located_in")]
RULES_BY_NAME = {r.name: r for r in DEFAULT_RULES}


def recheck(fact: Tuple[str, str, str], rule_name: str,
            premises: Sequence[Tuple[str, str, str]]) -> bool:
    """Rerun one derivation step symbolically: do the premises, under the
    rule, yield exactly this fact?  Needs no trust in the reasoner."""
    rule = RULES_BY_NAME.get(rule_name)
    if rule is None or len(premises) != len(rule.body):
        return False
    b: Dict[str, str] = {}
    for pat, p in zip(rule.body, premises):
        for t, val in zip(pat, p):
            if t.startswith("?"):
                if b.setdefault(t, val) != val:
                    return False
            elif t != val:
                return False
    return tuple(b.get(t, t) for t in rule.head) == tuple(fact)


def recheck_kb(kb, check: str, fid: Optional[str] = None) -> Optional[bool]:
    """knowledge.py checker for 'reason:<rule>:<fid>,<fid>'. The fact being
    checked is looked up as the one carrying this check string."""
    try:
        _, rule_name, fids = check.split(":", 2)
        prem_ids = [p for p in fids.split(",") if p]
        prem = [kb.facts_[p] for p in prem_ids]
    except (ValueError, KeyError):
        return None
    targets = [f for f in kb.facts_.values() if f.get("check") == check]
    if fid is not None:
        targets = [kb.facts_[fid]]
    if not targets:
        return None
    t = targets[0]
    return recheck((t["s"], t["r"], t["o"]), rule_name, [(p["s"], p["r"], p["o"]) for p in prem])


def check_imports(kb, check: str, fid: Optional[str] = None) -> Optional[bool]:
    """'imports:<path under control-numpy>:<module>' -- does that source file
    import that module?  The code itself is the world that grades the claim."""
    import ast
    try:
        _, path, mod = check.split(":", 2)
        src = (HERE.parent / path).resolve()
        if HERE.parent not in src.parents:
            return None
        tree = ast.parse(src.read_text())
    except (ValueError, OSError, SyntaxError):
        return None
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            names.add(n.module.split(".")[0])
    return mod in names


def check_grep(kb, check: str, fid: Optional[str] = None) -> Optional[bool]:
    """'grep:<path under control-numpy>:<text>' -- does the file contain text?"""
    try:
        _, path, text = check.split(":", 2)
        src = (HERE.parent / path).resolve()
        if HERE.parent not in src.parents:
            return None
        return text in src.read_text()
    except (ValueError, OSError):
        return None


try:  # plug into memory's KB so kb.reproduce(agent, fid) reruns derivations
    import knowledge as _K  # noqa: E402
    if hasattr(_K, "register_checker"):
        _K.register_checker("reason", recheck_kb)
        _K.register_checker("imports", check_imports)
        _K.register_checker("grep", check_grep)
except Exception:  # pragma: no cover
    pass


# ---------------------------------------------------------------- calibration fit

def synthetic_queries(n: int, rng: np.random.Generator, vocab_size: int = 300,
                      max_leaves: int = 1500, absent_frac: float = 0.3):
    """Slot queries against frames of 1..max_leaves slots (load drives noise);
    absent_frac of queries ask for a role that is not in the frame (the right
    answer is 'unknown', so the top-1 guess counts as wrong)."""
    vocab = [f"w{i}" for i in range(vocab_size)]
    roles = [f"r{i}" for i in range(max_leaves + 20)]
    book = Codebook(vocab)
    Rv = np.stack([L.role(r) for r in roles]).astype(np.int32)
    Fv = np.stack([filler_key(w) for w in vocab]).astype(np.int32)
    out = []
    for _ in range(n):
        k = int(np.exp(rng.uniform(0, np.log(max_leaves))))
        rs = rng.choice(len(roles), k, replace=False)
        fs = rng.choice(vocab_size, k)
        s = (Rv[rs] * Fv[fs]).sum(0) + L.atom(L.FRAME).astype(np.int32)
        rec = np.where(s > 0, 1, np.where(s < 0, -1, L.atom(L.TIE))).astype(np.int8)
        if rng.random() < absent_frac:
            used = set(rs.tolist())
            q = int(rng.choice([i for i in range(len(roles)) if i not in used]))
            truth = None
        else:
            j = int(rng.integers(k))
            q, truth = int(rs[j]), vocab[fs[j]]
        top = book.top(np.roll(L.bind(rec, L.role(roles[q])), -1), 2)
        out.append((top[0][1] - max(top[1][1], 0.0), top[0][0] == truth, k, top[0][1]))
    return out


def fit_calibration(n: int = 4000, seed: int = 0, save: bool = True) -> Calibrator:
    q = synthetic_queries(n, np.random.default_rng(seed))
    hi = [(g, c) for g, c, _, z in q if z >= Z_FLOOR]
    lo = [c for g, c, _, z in q if z < Z_FLOOR]
    cal = Calibrator.fit([g for g, _ in hi], [c for _, c in hi])
    cal.p_low = (sum(lo) + 0.5) / (len(lo) + 1.0)
    if save:
        CALIB_FILE.write_text(json.dumps(cal.to_json()))
    return cal
