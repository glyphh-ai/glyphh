"""knowledge.py -- the group's shared, graded knowledge base (owner: memory).

A fact is a SENTENCE in the group language (shared/language.py):

    (assert :subj s :rel r :obj o)

A grade is a sentence too, nesting the fact it grades:

    (grade :content (assert :subj s :rel r :obj o) :obj yes|no :agent g :why how)

The KB is an append-only event log (shared/kb.jsonl). Each line carries
the PACKED HYPERVECTOR of its sentence (wire form, 1024 bytes b64) plus its
text surface; on replay the vector is decoded with the shared lexicon and
the decoded meaning is what the KB believes. Every agent replays the same
log, so the KB is the group's memory, not one agent's. Nothing is deleted:
knowledge is only graded down.

"The world grades it" (see LANGUAGE.md, Memory & learning):
  * a claim is worth nothing until an agent OTHER than its teller has
    reproduced it: re-ran its `check`, observed it independently, or
    told the same triple on its own (independent confirmation);
  * self-grades are rejected (ValueError);
  * trust = mean of Beta(1 + ok, 1 + bad) over outside grades;
  * ask() only answers from facts with trust >= 0.6 and >= 1 outside ok;
  * a derived fact (trail=[premise fids]) is capped by its weakest
    premise until an outside agent reproduces it directly.

API
    kb = KB()                                   # shared/kb.jsonl + shared vocab
    kb = KB(tmp_path, lex=Lexicon(path=None))   # private (tests / simulations)
    fid = kb.tell(agent, s, r, o, check=None, trail=None)
    kb.grade(agent, fid, ok, how="reproduced")
    kb.reproduce(agent, fid) -> bool | None     # re-run a fact's check, grade it
    kb.ask(s, r)  -> Answer(obj, conf, fid, status, sim)  status answered|uncertain
    kb.ingest(channel_msg) -> fid | None        # apply a (assert ..)/(grade ..) payload
    kb.query(s=None, r=None, o=None) -> list[dict]
    kb.facts(min_trust=0.0) -> iter of (fid, s, r, o, trust)
    kb.ungraded(agent) -> list[dict]            # facts `agent` may still grade
    kb.stats()
    add_fact(s, r, o, source, ...)              # alias for reasoner

Checks (reproducible claims): "expr:<arithmetic comparison>" is re-run by a
tiny safe evaluator; "lang:<s-expression>" claims the sentence round-trips
encode->decode; other agents plug their own with register_checker(prefix, fn)
(e.g. reasoner's "reason:" derivations).
"""

from __future__ import annotations

import ast
import base64
import fcntl
import hashlib
import json
import operator
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import numpy as np

import sys as _sys
if str(Path(__file__).resolve().parent) not in _sys.path:
    _sys.path.insert(0, str(Path(__file__).resolve().parent))
import language as L  # noqa: E402  shared/language.py (lexicon)

HERE = Path(__file__).resolve().parent
DEFAULT_LOG = HERE / "kb.jsonl"

TRUST_ANSWER = 0.6      # a fact must reach this trust to be used as an answer
                        # (one fresh grader's ok: (1+0.5)/(2+0.5) = 0.6 -> just enough)
MIN_OUTSIDE = 1         # ... and have at least this many outside ok-grades

_CHECKERS: Dict[str, Callable[["KB", str], Optional[bool]]] = {}


def register_checker(prefix: str, fn: Callable[["KB", str], Optional[bool]]):
    """Other agents plug in reproducers: check strings 'prefix:...' are
    re-run by fn(kb, check) -> True/False/None(can't tell)."""
    _CHECKERS[prefix] = fn


# ---------------------------------------------------------------- checks
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
        ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


def _safe_eval(expr: str):
    """Tiny arithmetic/comparison evaluator (no names, no calls)."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 64:
                raise ValueError("exponent too large")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _OPS:
            return _OPS[type(n.ops[0])](ev(n.left), ev(n.comparators[0]))
        raise ValueError(f"not allowed: {ast.dump(n)[:60]}")
    return ev(ast.parse(expr, mode="eval"))


def _check_expr(kb: "KB", check: str) -> Optional[bool]:
    try:
        return bool(_safe_eval(check.split(":", 1)[1]))
    except Exception:
        return None


def _check_lang(kb: "KB", check: str) -> Optional[bool]:
    """lang:<text surface>  -- the claim is that the text round-trips."""
    try:
        text = check.split(":", 1)[1]
        m = L.parse(text)
        back = L.decode(L.encode(m, kb.lex, persist=False), kb.lex)
        return _norm(back) == _norm(m)   # role names compared case-insensitively
    except Exception:
        return None


def _norm(m):
    if isinstance(m, dict):
        return {str(k).lower(): _norm(v) for k, v in m.items()}
    if isinstance(m, (list, tuple)):
        return [_norm(v) for v in m]
    return str(m)


def _check_kbcurve(kb: "KB", check: str) -> Optional[bool]:
    """kbcurve:<seed>:<steps>:<metric>:<op>:<value>[:<bad_mode>] -- re-run
    memory's learning-curve simulation (memory/curve.py) and compare the
    final-step metric, e.g. kbcurve:0:300:wrong:<=:0.0"""
    try:
        import importlib.util
        parts = check.split(":")
        seed, steps, metric, op, val = int(parts[1]), int(parts[2]), parts[3], parts[4], float(parts[5])
        mode = parts[6] if len(parts) > 6 else None
        spec = importlib.util.spec_from_file_location(
            "memory_curve", str(HERE.parent / "memory" / "curve.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        row = mod.run(seed=seed, steps=steps, log_every=steps,
                      bad_grader="lexicon" if mode else None, bad_mode=mode or "random")[-1]
        return bool(_safe_eval(f"{row[metric]!r} {op} {val!r}"))
    except Exception:
        return None


register_checker("kbcurve", _check_kbcurve)


def _checker(prefix: str):
    """Find the checker for a prefix; lazily import the other agents' modules
    (protocol registers proto:, reason registers reason:) the first time."""
    if prefix not in _CHECKERS:
        import importlib
        for mod in ("protocol", "reason"):
            try:
                importlib.import_module(mod)
            except Exception:
                pass
    return _CHECKERS.get(prefix)


register_checker("expr", _check_expr)
register_checker("lang", _check_lang)


# ---------------------------------------------------------------- model
FACT_ACTS = ("assert", "tell", "fact", "answer")


def fact_meaning(s: str, r: str, o: str) -> dict:
    return {"act": "assert", "subj": s, "rel": r, "obj": o}


def grade_meaning(agent: str, s: str, r: str, o: str, ok: bool, how: str) -> dict:
    """A grade is itself a sentence: (grade :content (assert ...) :obj yes :agent g :why how)"""
    return {"act": "grade", "content": fact_meaning(s, r, o), "obj": "yes" if ok else "no",
            "agent": agent, "why": how}


def fact_id(s: str, r: str, o: str) -> str:
    """Same triple -> same id, whoever tells it. Independent tells of the
    same triple are therefore confirmations of one fact."""
    return hashlib.sha256(f"{s}\x1f{r}\x1f{o}".encode()).hexdigest()[:12]


def _b64(v: np.ndarray) -> str:
    return base64.b64encode(L.to_wire(v).tobytes()).decode()


def _unb64(s: str) -> np.ndarray:
    return L.from_wire(np.frombuffer(base64.b64decode(s), np.uint8))


@dataclass
class Answer:
    obj: Optional[str]
    conf: float           # trust of the fact that answered (0 if uncertain)
    fid: Optional[str]
    status: str           # "answered" | "uncertain"
    sim: float = 0.0      # language-level slot match (subj + rel) of question to fact

    def __iter__(self):
        return iter((self.obj, self.conf))


class KB:
    """The log carries the LANGUAGE: every event stores the packed hypervector
    of its meaning ("wire") plus its text surface. On replay the vector is
    decoded with the shared lexicon; the decoded meaning is authoritative
    (the text is kept only for humans and to count decode mismatches)."""

    def __init__(self, path: Optional[Path] = None, lex=None, weighted: bool = True):
        self.weighted = weighted
        self._rep: Optional[Dict[str, float]] = None
        self.path = Path(path) if path else DEFAULT_LOG
        self.lex = lex or L.default_lexicon()
        self.persist = self.lex.path is not None
        self.facts_: Dict[str, dict] = {}
        self.order: List[str] = []
        self.vecs: Dict[str, np.ndarray] = {}
        self._pos = 0
        self._mat: Optional[np.ndarray] = None
        self._mat_ids: List[str] = []
        self.decode_ok = 0
        self.decode_bad = 0
        self.refresh()

    # ------------------------------------------------------------ log io
    def _append(self, ev: dict):
        ev = {"ts": time.time(), **ev}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(ev) + "\n")
            fcntl.flock(f, fcntl.LOCK_UN)
        self.refresh()

    def refresh(self):
        """Replay any new events from the shared log (other agents' too)."""
        if not self.path.exists():
            return
        with self.path.open() as f:
            f.seek(self._pos)
            data = f.read()
            self._pos = f.tell()
        if data and self.persist:
            self.lex.reload()
        for line in data.splitlines():
            if line.strip():
                try:
                    self._apply(json.loads(line))
                except (ValueError, KeyError, TypeError):
                    self.decode_bad += 1

    def _read_event(self, ev: dict) -> Optional[dict]:
        """Decode the event's hypervector back into a meaning."""
        v = _unb64(ev["wire"])
        m = L.read_back(v, self.lex).meaning
        if isinstance(m, dict) and m == L.canonical(L.parse(ev.get("text", "()x"))):
            self.decode_ok += 1
        else:
            self.decode_bad += 1
        return (m if isinstance(m, dict) else None), v

    def _apply(self, ev: dict):
        self._rep = None
        m, v = self._read_event(ev)
        if m is None:
            return
        agent = ev["agent"]
        if m.get("act") in FACT_ACTS:
            s, r, o = m.get("subj"), m.get("rel"), m.get("obj")
            if not all(isinstance(x, str) for x in (s, r, o)):
                return
            fid = fact_id(s, r, o)
            f = self.facts_.get(fid)
            if f is None:
                f = {"fid": fid, "s": s, "r": r, "o": o, "text": L.show(m),
                     "source": agent, "tellers": [], "check": ev.get("check"),
                     "trail": ev.get("trail"), "grades": {}, "ts": ev["ts"],
                     "via": ev.get("via")}
                self.facts_[fid] = f
                self.order.append(fid)
                self.vecs[fid] = L.encode(fact_meaning(s, r, o), self.lex, persist=False)
                self._mat = None
            if agent not in f["tellers"]:
                f["tellers"].append(agent)
                if agent != f["source"]:
                    # independent tell of the same triple = confirmation
                    f["grades"].setdefault(agent, (True, "confirmed"))
            if not f["check"] and ev.get("check"):
                f["check"] = ev["check"]
        elif m.get("act") == "grade":
            c = m.get("content")
            if not isinstance(c, dict):
                return
            fid = fact_id(c.get("subj"), c.get("rel"), c.get("obj"))
            f = self.facts_.get(fid)
            if f is not None and agent != f["source"] and m.get("obj") in ("yes", "no"):
                f["grades"][agent] = (m["obj"] == "yes", m.get("why", ""))

    # ------------------------------------------------------------ writes
    def _say(self, m: dict) -> dict:
        v = L.encode(m, self.lex, persist=self.persist)
        return {"text": L.show(m), "wire": _b64(v)}

    def tell(self, agent: str, s: str, r: str, o: str, check: Optional[str] = None,
             trail: Optional[List[str]] = None, via: Optional[str] = None) -> str:
        """`via`: who wrote the event on the speaker's behalf (a relay, e.g.
        courier's to_kb); recorded, never counted as a grade."""
        fid = fact_id(s, r, o)
        ev = {"ev": "tell", "agent": agent, **self._say(fact_meaning(s, r, o)),
              "check": check, "trail": trail}
        if via and via != agent:
            ev["via"] = via
        self._append(ev)
        return fid

    def grade(self, agent: str, fid: str, ok: bool, how: str = "reproduced"):
        f = self.facts_.get(fid)
        if f is None:
            self.refresh()
            f = self.facts_.get(fid)
        if f is None:
            raise KeyError(fid)
        if agent == f["source"]:
            raise ValueError("self-grading is not allowed: the world grades a claim")
        self._append({"ev": "grade", "agent": agent,
                      **self._say(grade_meaning(agent, f["s"], f["r"], f["o"], ok, how))})

    def ingest(self, msg: dict) -> Optional[str]:
        """Take a channel message whose payload is a sentence in the language
        and apply it: (assert :subj :rel :obj) -> tell by msg sender;
        (grade :content (assert ...) :obj yes|no) -> grade. Also unwraps a
        courier envelope that carries the sentence in :content. Returns the
        fid touched, or None if the payload is not knowledge."""
        if msg.get("payload") is None:
            return None
        self.lex.reload()
        m = L.read_back(msg["payload"], self.lex).meaning
        if not isinstance(m, dict):
            return None
        who = msg["from"]
        # unwrap protocol envelopes (courier): the sentence rides in :content
        for _ in range(3):
            inner = m.get("content")
            if not isinstance(inner, dict):
                break
            envelope = m.get("check") == "proto_v1" or (
                "subj" not in m and m.get("act") != "grade") or (
                m.get("act") == "grade" and inner.get("act") == "grade")
            if not envelope:
                break
            m = inner
        act = m.get("act", "assert")
        if act == "grade" and isinstance(m.get("content"), dict):
            c = m["content"]
            if not all(isinstance(c.get(k), str) for k in ("subj", "rel", "obj")):
                return None
            fid = fact_id(c["subj"], c["rel"], c["obj"])
            if fid in self.facts_ and self.facts_[fid]["source"] != who:
                ok = m.get("obj") in ("yes", "ok", "true", "agree")
                self.grade(who, fid, ok, m.get("why", "reproduced"))
                return fid
            return None
        if act in FACT_ACTS and all(isinstance(m.get(k), str) for k in ("subj", "rel", "obj")) \
                and m.get("obj") not in ("?", "unknown"):
            return self.tell(who, m["subj"], m["rel"], m["obj"])
        return None

    def reproduce(self, agent: str, fid: str) -> Optional[bool]:
        """Re-run the fact's check as `agent`; grade it if the check decides."""
        f = self.facts_[fid]
        chk = f.get("check")
        if not chk:
            return None
        fn = _checker(chk.split(":", 1)[0])
        res = None
        if fn:
            try:
                res = fn(self, chk, fid)      # checkers may take the fid (reasoner's does)
            except TypeError:
                res = fn(self, chk)
        if res is not None and agent != f["source"]:
            self.grade(agent, fid, res, how="reproduced")
        return res

    # ------------------------------------------------------------ trust
    def reputation(self, agent: str) -> float:
        """How far the group can trust `agent` AS A GRADER, learned from use:
        agreement of its grades with the majority of the OTHER graders of the
        same fact. Prior Beta(3,1) (graders start mostly trusted, rep 0.75);
        a grader that agrees at chance drifts to 0.5 and loses all weight."""
        if self._rep is None:
            agree: Dict[str, int] = {}
            n: Dict[str, int] = {}
            for f in self.facts_.values():
                gs = f["grades"]
                if len(gs) < 2:
                    continue
                for a, (g, _) in gs.items():
                    others = [o for b, (o, _) in gs.items() if b != a]
                    yes = sum(others)
                    if 2 * yes == len(others):
                        continue
                    n[a] = n.get(a, 0) + 1
                    agree[a] = agree.get(a, 0) + (g == (2 * yes > len(others)))
            self._rep = {a: (3 + agree[a]) / (4 + n[a]) for a in n}
        return self._rep.get(agent, 0.75)

    def weight(self, agent: str) -> float:
        """Grade weight = 2*rep - 1 (rep 0.75 -> 0.5; chance -> 0), unless
        weighting is off (then every outside grade counts 1)."""
        if not self.weighted:
            return 1.0
        return max(0.0, 2 * self.reputation(agent) - 1)

    def trust(self, fid: str, _seen=None) -> float:
        f = self.facts_[fid]
        ok = sum(self.weight(a) for a, (g, _) in f["grades"].items() if g)
        bad = sum(self.weight(a) for a, (g, _) in f["grades"].items() if not g)
        t = (1 + ok) / (2 + ok + bad)
        direct = any(g and how in ("reproduced", "confirmed")
                     for g, how in f["grades"].values())
        if f.get("trail") and not direct:
            seen = _seen or set()
            seen.add(fid)
            prem = [self.trust(p, seen) for p in f["trail"]
                    if p in self.facts_ and p not in seen]
            if prem:
                t = min(t, min(prem))
        return t

    def outside_ok(self, fid: str) -> int:
        return sum(1 for g, _ in self.facts_[fid]["grades"].values() if g)

    def trusted(self, fid: str) -> bool:
        return self.trust(fid) >= TRUST_ANSWER and self.outside_ok(fid) >= MIN_OUTSIDE

    # ------------------------------------------------------------ reads
    def facts(self, min_trust: float = 0.0):
        self.refresh()
        for fid in self.order:
            f = self.facts_[fid]
            t = self.trust(fid)
            if t >= min_trust:
                yield fid, f["s"], f["r"], f["o"], t

    def query(self, s=None, r=None, o=None) -> List[dict]:
        self.refresh()
        out = []
        for fid in self.order:
            f = self.facts_[fid]
            if (s is None or f["s"] == s) and (r is None or f["r"] == r) and \
               (o is None or f["o"] == o):
                out.append({"fid": fid, "s": f["s"], "r": f["r"], "o": f["o"],
                            "source": f["source"], "trust": self.trust(fid),
                            "graded": len(f["grades"]), "trail": f["trail"],
                            "check": f["check"]})
        return out

    def ungraded(self, agent: str) -> List[dict]:
        return [q for q in self.query() if q["source"] != agent
                and agent not in self.facts_[q["fid"]]["grades"]]

    def vector(self, fid: str) -> np.ndarray:
        return self.vecs[fid]

    def _matrix(self):
        if self._mat is None or len(self._mat_ids) != len(self.order):
            self._mat_ids = list(self.order)
            if self._mat_ids:
                self._mat = np.stack([self.vecs[i] for i in self._mat_ids]).astype(np.float32)
            else:
                self._mat = np.zeros((0, self.lex.dim), np.float32)
        return self._mat, self._mat_ids

    def slot_match(self, s: str, r: str) -> np.ndarray:
        """Per stored fact: min(sim(subj slot, s), sim(rel slot, r)) computed by
        unbinding the roles from the fact matrix -- a query in the language."""
        M, ids = self._matrix()
        if not ids:
            return np.zeros(0, np.float32)
        D = self.lex.dim
        us = np.roll(M * L.role("subj", D)[None, :], -1, axis=1) @ L.atom(s, D).astype(np.float32)
        ur = np.roll(M * L.role("rel", D)[None, :], -1, axis=1) @ L.atom(r, D).astype(np.float32)
        return np.minimum(us, ur) / D

    def ask(self, s: str, r: str) -> Answer:
        """Answer (ask :subj s :rel r :obj ?) in the language: rank facts by
        slot match, keep those whose subj AND rel slots clear the noise
        threshold, and answer from the most trusted one by unbinding its obj
        slot and cleaning it up against the vocabulary. Nothing trusted ->
        uncertain (never a guess)."""
        self.refresh()
        sims = self.slot_match(s, r)
        if not len(sims):
            return Answer(None, 0.0, None, "uncertain")
        tau = self.lex.threshold()
        M, ids = self._matrix()
        hits = [i for i in np.flatnonzero(sims > tau) if self.trusted(ids[i])]
        if not hits:
            return Answer(None, 0.0, None, "uncertain")
        best = max(hits, key=lambda i: (self.trust(ids[i]), sims[i]))
        obj, _ = self.lex.cleanup(L.unbind_role(M[best].astype(np.int8), "obj", dim=self.lex.dim))
        return Answer(obj, self.trust(ids[best]), ids[best], "answered", float(sims[best]))

    def ask_all(self, s: str, r: str) -> List[Answer]:
        """Every trusted answer to (s r ?), most trusted first -- for relations
        with many values (depends_on, part_of). Same language path as ask()."""
        self.refresh()
        sims = self.slot_match(s, r)
        M, ids = self._matrix()
        tau = self.lex.threshold()
        hits = [i for i in np.flatnonzero(sims > tau) if self.trusted(ids[i])]
        out = []
        for i in sorted(hits, key=lambda i: (-self.trust(ids[i]), -sims[i])):
            obj, _ = self.lex.cleanup(L.unbind_role(M[i].astype(np.int8), "obj", dim=self.lex.dim))
            out.append(Answer(obj, self.trust(ids[i]), ids[i], "answered", float(sims[i])))
        return out

    # ------------------------------------------------------------ citing facts
    def cite(self, fid: str) -> np.ndarray:
        """A fact's CITATION vector: atom("fact:"+fid), an embedded vector (like
        courier's msg ids) so fids never enter vocab.txt. Put it in a :because
        slot; any reader holding the KB resolves it back with resolve()."""
        return L.atom("fact:" + fid, self.lex.dim)

    def resolve(self, v: np.ndarray) -> Optional[str]:
        """Citation vector (possibly unbound from a sentence, noisy) -> fid."""
        self.refresh()
        if not self.order:
            return None
        C = np.stack([self.cite(f) for f in self.order]).astype(np.float32)
        s = C @ np.asarray(v, np.float32) / (np.linalg.norm(v) * np.sqrt(self.lex.dim) + 1e-12)
        i = int(np.argmax(s))
        return self.order[i] if s[i] >= self.lex.threshold() else None

    # ------------------------------------------------------------ stats
    def stats(self) -> dict:
        self.refresh()
        n = len(self.order)
        graded = sum(1 for i in self.order if self.facts_[i]["grades"])
        trusted = sum(1 for i in self.order if self.trusted(i))
        refuted = sum(1 for i in self.order if self.trust(i) < 0.5)
        return {"facts": n, "graded": graded, "trusted": trusted, "refuted": refuted,
                "decode_ok": self.decode_ok, "decode_bad": self.decode_bad}

    # reasoner-friendly aliases
    def add_fact(self, s, r, o, source, conf=None, trail=None, check=None):
        return self.tell(source, s, r, o, check=check, trail=trail)


def answer_handler(kb: KB):
    """protocol.serve() handler: answers (query :subj s :rel r :obj ?) with EVERY
    trusted value (a list when several), :conf from the top trust; abstains with
    obj=unknown when the KB is uncertain.  P.serve("memory", answer_handler(KB()))"""
    def h(c):
        if not isinstance(c, dict) or c.get("obj") != "?":
            return None
        s, r = c.get("subj"), c.get("rel")
        if not (isinstance(s, str) and isinstance(r, str)):
            return None
        ans = kb.ask_all(s, r)
        if not ans:
            return {"act": "fact", "subj": s, "rel": r, "obj": "unknown"}
        objs = [a.obj for a in ans]
        return {"act": "fact", "subj": s, "rel": r,
                "obj": objs[0] if len(objs) == 1 else objs,
                "conf": "conf_hi" if ans[0].conf >= 0.8 else "conf_mid"}
    return h
