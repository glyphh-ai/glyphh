"""The shared language (owner: lexicon). numpy + stdlib only.

A MEANING is a nested Python value:
    atom       : str                       e.g. "cat", "is_a", "?"
    frame      : dict {role: meaning}      e.g. {"subj": "cat", "rel": "is_a", "obj": "animal"}
    list       : list [meaning, ...]       ordered; roles "#0", "#1", ...
A REPRESENTATION is one bipolar hypervector: np.int8 array of shape (D,), values in {-1,+1}.

Grammar (how a meaning becomes a vector):
    enc(atom)         = atom_vec(atom)                            sha256-seeded, identical for everyone
    sum({r1: f1, ..}) = FRAME + sum_i  role(ri) * roll(sum(fi), 1)       (int32, unsigned)
    sum([f0, f1, ..]) = LIST  + sum_i  role("#i") * roll(sum(fi), 1)
    enc(m)            = sign(sum(m))       signed ONCE at the top; every leaf weighs 1
    an np.ndarray filler is embedded as-is (e.g. a quoted message vector), weight 1.
  * = bind (elementwise multiply, self-inverse); roll = permutation that marks
  "one level deeper", so {a:{b:x}} != {b:{a:x}}. FRAME / LIST are marker atoms
  that let the reader tell "this slot holds a sub-structure" from "this slot holds a word".
Reading (vector -> meaning): for every known role r, u = roll(v * role(r), -1);
  if u matches a known atom above threshold -> slot holds that atom;
  elif u matches FRAME/LIST -> recurse into u; else slot is empty.

Wire form: to_wire(v) = np.packbits(v > 0) -> uint8[D/8] (1024 bytes at D=8192).
Text surface (s-expression):  (assert :subj cat :rel is_a :obj animal)
    "(" head? (:role filler)* ")"   head fills role "act";  [a b c] is a list;
    "quoted words" are atoms with spaces.

Quick API:
    from language import Lexicon, encode, decode, read_back, parse, show, to_wire, from_wire
    lex = Lexicon()                      # loads shared/vocab.txt, knows every registered word/role
    v = encode(parse("(assert :subj cat :rel is_a :obj animal)"), lex)   # int8 (D,)
    decode(v, lex)                       # -> {'act':'assert','subj':'cat','rel':'is_a','obj':'animal'}
    r = read_back(v, lex); r.meaning, r.scores, r.confidence   # per-slot similarity scores
    payload = to_wire(v); v2 = from_wire(payload)
    lex.cleanup(vec) -> (name, sim);  sim(a, b);  atom(name);  bind/unbind/bundle/permute
"""

from __future__ import annotations

import fcntl
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np

VERSION = "1.1"
D = 8192                      # default dimension; every agent uses this unless told otherwise
SHARED = Path(__file__).resolve().parent
VOCAB_FILE = SHARED / "vocab.txt"

FRAME = "__frame__"           # marker: this vector is a frame (dict)
LIST = "__list__"             # marker: this vector is a list
TIE = "__tie__"               # tie-breaker added to even-sized bundles
MARKERS = (FRAME, LIST, TIE)

# ---------------------------------------------------------------- role inventory
# role -> gloss. Roles are vectors too (atom "role:<name>"), disjoint from words.
ROLES: Dict[str, str] = {
    # core proposition
    "act": "speech act / frame type (head of an s-expression)",
    "subj": "subject: what the statement is about",
    "rel": "relation / predicate",
    "obj": "object / value of the relation",
    "attr": "attribute name", "val": "attribute value",
    "not": "polarity: 'yes' = negated",
    "quant": "quantifier: all / some / none / n",
    # people and provenance
    "agent": "who did / claims it", "src": "source of a claim",
    "from": "sender", "to": "addressee",
    # discourse / protocol (courier)
    "re": "reply-to: the message this answers (nested or id atom)",
    "thread": "conversation thread", "seq": "sequence number",
    "id": "identifier", "check": "integrity / reproducibility check",
    "content": "nested content (a full meaning)", "topic": "what it is about",
    # knowledge and reasoning (memory, reasoner)
    "conf": "confidence bucket atom: conf_hi / conf_mid / conf_lo",
    "because": "premises / evidence (nested meaning or list)",
    "rule": "which inference rule produced it",
    "cond": "if-part", "then": "then-part",
    "name": "a name being defined", "def": "definition (nested meaning)",
    "time": "when", "loc": "where", "why": "reason / purpose",
}
MAX_POS = 32                  # list positions "#0".."#31"
POS_ROLES = [f"#{i}" for i in range(MAX_POS)]

ACTS = ["assert", "tell", "ask", "answer", "define", "propose", "agree", "disagree",
        "ack", "done", "grade", "fact", "rule", "query"]
BASE_WORDS = ACTS + ["?", "unknown", "yes", "no", "true", "false",
                     "conf_hi", "conf_mid", "conf_lo", "all", "some", "none",
                     "lexicon", "courier", "memory", "reasoner", "orchestrator"]

Meaning = Union[str, Dict[str, Any], List[Any]]

# ---------------------------------------------------------------- vector algebra
_cache: Dict[Tuple[str, int], np.ndarray] = {}


def atom(name: str, dim: int = D) -> np.ndarray:
    """Deterministic bipolar vector for a word. sha256(name) seeds numpy's PCG64."""
    key = (name, dim)
    v = _cache.get(key)
    if v is None:
        seed = int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest()[:8], "little")
        v = (np.random.default_rng(seed).integers(0, 2, dim, dtype=np.int8) * 2 - 1).astype(np.int8)
        v.setflags(write=False)
        _cache[key] = v
    return v


def role(name: str, dim: int = D) -> np.ndarray:
    """Role vectors are case-insensitive: role("SUBJ") is role("subj")."""
    return atom("role:" + name.lower(), dim)


class Frame(dict):
    """A decoded frame. Keys are canonical lowercase roles, but lookup is
    case-insensitive (f["SUBJ"] == f["subj"]) and equality ignores role case, so
    code written with {"SUBJ": ...} keeps working."""

    def __getitem__(self, k):
        return dict.__getitem__(self, k.lower() if isinstance(k, str) else k)

    def get(self, k, default=None):
        return dict.get(self, k.lower() if isinstance(k, str) else k, default)

    def __contains__(self, k):
        return dict.__contains__(self, k.lower() if isinstance(k, str) else k)

    def __eq__(self, other):
        if isinstance(other, dict):
            return canonical(dict(self)) == canonical(other)
        return NotImplemented

    def __ne__(self, other):
        r = self.__eq__(other)
        return r if r is NotImplemented else not r

    __hash__ = None


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a * b).astype(np.int8)


unbind = bind                 # bipolar binding is its own inverse


def permute(v: np.ndarray, k: int = 1) -> np.ndarray:
    return np.roll(v, k)


def bundle(vs: Sequence[np.ndarray], dim: Optional[int] = None) -> np.ndarray:
    """Majority vote. Even counts get the TIE vector added so the sign is never 0."""
    vs = list(vs)
    if not vs:
        raise ValueError("empty bundle")
    dim = dim or len(vs[0])
    s = np.sum(np.stack(vs).astype(np.int32), axis=0)
    if len(vs) % 2 == 0:
        s = s + atom(TIE, dim)
    return np.where(s >= 0, 1, -1).astype(np.int8)


def sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity (for bipolar vectors = dot / D). Random pairs: ~N(0, 1/D)."""
    a = a.astype(np.float32); b = b.astype(np.float32)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def to_wire(v: np.ndarray) -> np.ndarray:
    """Bipolar vector -> packed bits (uint8, D/8 bytes). Attach this as a channel payload."""
    return np.packbits(np.asarray(v) > 0)


def from_wire(p: np.ndarray, dim: int = D) -> np.ndarray:
    """Packed bits (or an int8 bipolar vector) -> int8 bipolar vector."""
    p = np.asarray(p)
    if p.dtype == np.uint8 and p.size * 8 == dim:
        return (np.unpackbits(p)[:dim].astype(np.int8) * 2 - 1).astype(np.int8)
    return np.where(p.astype(np.float32) >= 0, 1, -1).astype(np.int8)


# ---------------------------------------------------------------- lexicon
class Lexicon:
    """The set of words and roles a reader knows. Words are shared via shared/vocab.txt
    (one entry per line; lines starting with ':' are roles). Encoding a meaning with
    persist=True appends its new words so every other agent can read them back."""

    def __init__(self, dim: int = D, path: Optional[Path] = VOCAB_FILE, load: bool = True):
        self.dim = dim
        self.path = Path(path) if path else None
        self.words: List[str] = []
        self._wset = set()
        self.roles: List[str] = []
        self._rset = set()
        self._A = None; self._R = None
        for r in list(ROLES) + POS_ROLES:
            self._add_role(r)
        for w in BASE_WORDS:
            self._add_word(w)
        if load:
            self.reload()

    # -- registry
    def _add_word(self, w: str) -> bool:
        if w in self._wset or w in MARKERS:
            return False
        self._wset.add(w); self.words.append(w); self._A = None
        return True

    def _add_role(self, r: str) -> bool:
        r = r.lower()
        if r in self._rset:
            return False
        self._rset.add(r); self.roles.append(r); self._R = None
        return True

    def reload(self) -> "Lexicon":
        """Pick up words other agents registered since we loaded."""
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.rstrip("\n")
                if not line:
                    continue
                if line.startswith(":"):
                    self._add_role(line[1:])
                else:
                    self._add_word(line)
        return self

    def learn(self, words: Iterable[str] = (), roles: Iterable[str] = (), persist: bool = True) -> List[str]:
        """Register words/roles. persist=True appends new ones to shared/vocab.txt."""
        new = [w for w in words if self._add_word(w)]
        new_r = [r for r in roles if self._add_role(r)]
        if persist and self.path and (new or new_r):
            with self.path.open("a", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                for w in new:
                    f.write(w.replace("\n", " ") + "\n")
                for r in new_r:
                    f.write(":" + r + "\n")
                fcntl.flock(f, fcntl.LOCK_UN)
        return new + [":" + r for r in new_r]

    def __contains__(self, w: str) -> bool:
        return w in self._wset

    # -- matrices (float32 for BLAS)
    @property
    def A(self) -> np.ndarray:
        if self._A is None:
            self._A = np.stack([atom(w, self.dim) for w in self.words]).astype(np.float32)
        return self._A

    @property
    def R(self) -> np.ndarray:
        if self._R is None:
            self._R = np.stack([role(r, self.dim) for r in self.roles]).astype(np.float32)
        return self._R

    def cleanup(self, v: np.ndarray, candidates: Optional[Sequence[str]] = None,
                k: int = 1) -> Union[Tuple[str, float], List[Tuple[str, float]]]:
        """Nearest known word(s) to v. Returns (name, sim) or, for k>1, a list of them."""
        v = np.asarray(v, dtype=np.float32)
        if candidates is None:
            names, M = self.words, self.A
        else:
            names = list(candidates)
            M = np.stack([atom(c, self.dim) for c in names]).astype(np.float32)
        s = M @ v / (np.linalg.norm(v) * np.sqrt(self.dim) + 1e-12)
        idx = np.argsort(-s)[:k]
        out = [(names[i], float(s[i])) for i in idx]
        return out[0] if k == 1 else out

    def threshold(self) -> float:
        """Default acceptance threshold: 6 sigma of random-pair noise."""
        return 6.0 / np.sqrt(self.dim)


_default_lex: Optional[Lexicon] = None


def default_lexicon() -> Lexicon:
    global _default_lex
    if _default_lex is None:
        _default_lex = Lexicon()
    return _default_lex


# ---------------------------------------------------------------- meaning -> vector
def words_of(m: Meaning) -> Tuple[List[str], List[str]]:
    """All atoms and roles used in a meaning."""
    ws: List[str] = []; rs: List[str] = []
    def walk(x):
        if isinstance(x, str):
            ws.append(x)
        elif isinstance(x, dict):
            for r, f in x.items():
                rs.append(r); walk(f)
        elif isinstance(x, (list, tuple)):
            for f in x:
                walk(f)
        elif isinstance(x, np.ndarray):
            pass                                  # an embedded vector (e.g. a quoted message)
        else:
            raise TypeError(f"not a meaning: {x!r}")
    walk(m)
    return ws, [r.lower() for r in rs if not r.startswith("#")]


def leaf_count(m: Meaning) -> int:
    """Capacity cost of a meaning: atoms + embedded vectors + one marker per frame/list."""
    if isinstance(m, (str, np.ndarray)):
        return 1
    vals = m.values() if isinstance(m, dict) else m
    return 1 + sum(leaf_count(x) for x in vals)


def max_leaves(dim: int = D) -> int:
    """Measured reliable budget (lexicon/capacity.py, default reader with peeling):
    nested proofs decode 100% up to 109 leaves and 0% at 129; flat frames 100% up to
    161 leaves (D=8192). Budget = D/80 = 102 at D=8192. (One-pass reader: ~D/128.)"""
    return dim // 80


def encode(m: Meaning, lex: Optional[Lexicon] = None, persist: bool = True) -> np.ndarray:
    """Meaning -> int8 hypervector. New words/roles are registered in the lexicon
    (and, with persist=True, appended to shared/vocab.txt for everyone).
    Warns if the meaning exceeds the measured leaf budget (max_leaves)."""
    lex = lex or default_lexicon()
    n = leaf_count(m)
    if n > max_leaves(lex.dim):
        import warnings
        warnings.warn(f"meaning has {n} leaves > budget {max_leaves(lex.dim)} at D={lex.dim}; "
                      "decode may drop slots. Split it, or quote parts as vectors.")
    ws, rs = words_of(m)
    lex.learn(ws, rs, persist=persist)
    return _enc(m, lex.dim)


def _enc(m: Meaning, dim: int) -> np.ndarray:
    """Top level: flat sum of every leaf, signed ONCE (see _sum)."""
    if isinstance(m, np.ndarray):
        return from_wire(m, dim)
    if isinstance(m, str):
        if m in MARKERS:
            raise ValueError(f"reserved marker {m}")
        return atom(m, dim)
    s = _sum(m, dim)
    return np.where(s > 0, 1, np.where(s < 0, -1, atom(TIE, dim))).astype(np.int8)


def _sum(m: Meaning, dim: int) -> np.ndarray:
    """Unsigned int32 superposition. Every leaf (atom, marker, embedded vector) has weight 1,
    so capacity is shared equally by all leaves no matter how deep they sit (measured:
    far better than signing at every level, see lexicon/capacity.py)."""
    if isinstance(m, np.ndarray):
        return from_wire(m, dim).astype(np.int32)
    if isinstance(m, str):
        if m in MARKERS:
            raise ValueError(f"reserved marker {m}")
        return atom(m, dim).astype(np.int32)
    if isinstance(m, (list, tuple)):
        if len(m) > MAX_POS:
            raise ValueError(f"list longer than {MAX_POS}")
        items = [(f"#{i}", f) for i, f in enumerate(m)]
        marker = LIST
    elif isinstance(m, dict):
        if not m:
            raise ValueError("empty frame")
        items = list(m.items())
        marker = FRAME
    else:
        raise TypeError(f"not a meaning: {m!r}")
    s = atom(marker, dim).astype(np.int32)
    for r, f in items:
        s = s + role(r, dim).astype(np.int32) * np.roll(_sum(f, dim), 1)
    return s


# ---------------------------------------------------------------- vector -> meaning
@dataclass
class Reading:
    meaning: Optional[Meaning]
    scores: Dict[str, float] = field(default_factory=dict)   # "subj", "content.obj", ... -> sim
    kind: str = "frame"                                        # frame | list | atom | noise

    @property
    def confidence(self) -> float:
        """Weakest slot similarity (0 if nothing read)."""
        return min(self.scores.values()) if self.scores else 0.0


def read_back(v: np.ndarray, lex: Optional[Lexicon] = None, tau: Optional[float] = None,
              max_depth: int = 6, peel: int = 4) -> Reading:
    """Vector -> Reading(meaning, per-slot scores, kind). Top level may be a frame,
    a list, or a bare atom. kind='noise' means nothing recognisable (foreign/garbled).

    peel = rounds of explaining-away: after a pass, the leaves already read are projected
    out of v (least squares) and the residual is read again, guided by what was found.
    Measured (lexicon/capacity.py): doubles-to-triples the leaf budget at no false-positive
    cost. peel=0 gives the plain one-pass reader."""
    lex = lex or default_lexicon()
    tau = lex.threshold() if tau is None else tau
    v = from_wire(v, lex.dim) if np.asarray(v).dtype == np.uint8 else np.asarray(v)
    scores: Dict[str, float] = {}
    fr = sim(v, atom(FRAME, lex.dim)); li = sim(v, atom(LIST, lex.dim))
    kind = "list" if li > fr else "frame"
    vf = v.astype(np.float32)
    if max(fr, li) < tau:
        # weak marker: a bare word, noise, or a frame so full its marker sank below tau
        name, s = lex.cleanup(v)
        if s >= tau:
            return Reading(name, {"": s}, "atom")
        node = _read(vf, lex, tau, max_depth, "", scores, kind)
        if _count(node) < 2:
            return Reading(None, {}, "noise")
    else:
        node = _read(vf, lex, tau, max_depth, "", scores, kind)
    n = _count(node)
    for _ in range(peel):
        B = np.stack(_leaf_vectors(node, lex.dim)).astype(np.float32)      # (F, D)
        coef, *_ = np.linalg.lstsq(B.T, vf, rcond=None)
        node = _read(vf - B.T @ coef, lex, tau, max_depth, "", scores, kind, guide=node)
        n2 = _count(node)
        if n2 == n:
            break
        n = n2
    node = _prune(vf, node, lex.dim, scores)
    return Reading(_finish(node), scores, kind)


def _prune(vf, node, dim, scores, ratio=0.5):
    """Drop word slots the whole reading does not need: fit v on every leaf read
    (least squares); a real leaf carries ~the same weight as the others, a chance
    6-sigma match carries only its noise. Slots with weight < ratio * median go."""
    paths: List[Tuple[str, ...]] = []
    vecs: List[np.ndarray] = []

    def walk(nd, ops):
        paths.append(None); vecs.append(_leaf_vectors((nd[0], {}), dim, ops)[0])
        for r, f in nd[1].items():
            if isinstance(f, tuple):
                walk(f, ops + (r,))
            else:
                x = atom(f, dim).astype(np.int32)
                for rr in reversed(ops + (r,)):
                    x = role(rr, dim).astype(np.int32) * np.roll(x, 1)
                paths.append(ops + (r,)); vecs.append(x)
    walk(node, ())
    if len(vecs) < 3:
        return node
    B = np.stack(vecs).astype(np.float32)
    coef, *_ = np.linalg.lstsq(B.T, vf, rcond=None)
    med = float(np.median(coef))
    drop = [p for p, c in zip(paths, coef) if p is not None and c < ratio * med]
    for p in drop:
        nd = node
        for r in p[:-1]:
            nd = nd[1][r]
        nd[1].pop(p[-1], None)
        scores.pop(".".join(p), None)
    return node


# internal parse node: (kind, {role: word | node})
def _count(node) -> int:
    return sum(1 + (_count(f) if isinstance(f, tuple) else 0) for f in node[1].values())


def _leaf_vectors(node, dim, ops=()):
    """The vector of every leaf of a parse node exactly as it sits inside sum(m)."""
    def place(x):
        for r in reversed(ops):
            x = role(r, dim).astype(np.int32) * np.roll(x, 1)
        return x
    out = [place(atom(LIST if node[0] == "list" else FRAME, dim).astype(np.int32))]
    for r, f in node[1].items():
        if isinstance(f, tuple):
            out += _leaf_vectors(f, dim, ops + (r,))
        else:
            x = atom(f, dim).astype(np.int32)
            for rr in reversed(ops + (r,)):
                x = role(rr, dim).astype(np.int32) * np.roll(x, 1)
            out.append(x)
    return out


def _finish(node):
    kind, out = node
    out = {r: (_finish(f) if isinstance(f, tuple) else f) for r, f in out.items()}
    if kind == "list":
        idx = sorted(int(r[1:]) for r in out)
        return [out[f"#{i}"] for i in range(len(idx))] if idx == list(range(len(idx))) else \
            Frame((r, out[r]) for r in sorted(out, key=lambda r: int(r[1:])))
    return Frame(out)


def _read(v, lex, tau, depth, path, scores, kind, guide=None):
    dim = lex.dim
    rnames = lex.roles
    known = dict(guide[1]) if guide else {}
    U = np.roll(lex.R * v[None, :], -1, axis=1)            # (R, D): candidate fillers
    nU = np.linalg.norm(U, axis=1, keepdims=True) + 1e-12
    S = (U @ lex.A.T) / (nU * np.sqrt(dim))                 # (R, N) word sims
    best = S.argmax(1); bests = S[np.arange(len(rnames)), best]
    mk = np.stack([atom(FRAME, dim), atom(LIST, dim)]).astype(np.float32)
    MS = (U @ mk.T) / (nU * np.sqrt(dim))                   # (R, 2) marker sims
    out: Dict[str, Any] = dict(known)
    for i, r in enumerate(rnames):
        if kind == "list" and not r.startswith("#"):
            continue
        if kind == "frame" and r.startswith("#"):
            continue
        p = f"{path}.{r}" if path else r
        g = known.get(r)
        if isinstance(g, str):
            continue                                        # already read
        if isinstance(g, tuple):                            # known sub-structure: look for more inside
            if depth > 1:
                out[r] = _read(U[i], lex, tau, depth - 1, p, scores, g[0], guide=g)
            continue
        ws, ms = bests[i], MS[i].max()
        if ws >= tau and ws >= ms:
            out[r] = lex.words[best[i]]; scores[p] = float(ws)
        elif ms >= tau and depth > 1:
            sub_kind = "list" if MS[i, 1] > MS[i, 0] else "frame"
            sub = _read(U[i], lex, tau, depth - 1, p, scores, sub_kind)
            if sub[1]:
                out[r] = sub; scores.setdefault(p, float(ms))
    return (kind, out)


def decode(v: np.ndarray, lex: Optional[Lexicon] = None, **kw) -> Optional[Meaning]:
    """Vector (int8 or packed uint8 wire form) -> meaning. None if unreadable."""
    return read_back(v, lex, **kw).meaning


def unbind_role(v: np.ndarray, *path: str, dim: int = D) -> np.ndarray:
    """Noisy filler at a role path, e.g. unbind_role(v, 'content', 'obj'). Clean it with lex.cleanup."""
    u = np.asarray(v)
    for r in path:
        u = permute(bind(u, role(r, dim)), -1)
    return u


def similarity(m1: Meaning, m2: Meaning, lex: Optional[Lexicon] = None) -> float:
    lex = lex or default_lexicon()
    return sim(encode(m1, lex), encode(m2, lex))


def canonical(m: Meaning) -> Meaning:
    """What decode() is expected to return for m (tuples -> lists)."""
    if isinstance(m, str):
        return m
    if isinstance(m, (list, tuple)):
        return [canonical(x) for x in m]
    if isinstance(m, np.ndarray):
        return m
    return {k.lower(): canonical(x) for k, x in m.items()}


# ---------------------------------------------------------------- text surface
_TOK = re.compile(r'\s*(?:(\()|(\))|(\[)|(\])|"((?:[^"\\]|\\.)*)"|([^\s()\[\]"]+))')


def _tokens(s: str):
    pos = 0
    s = s.strip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m or m.end() == pos:
            raise SyntaxError(f"bad text at {pos}: {s[pos:pos+20]!r}")
        pos = m.end()
        if m.group(1): yield ("(", None)
        elif m.group(2): yield (")", None)
        elif m.group(3): yield ("[", None)
        elif m.group(4): yield ("]", None)
        elif m.group(5) is not None: yield ("atom", bytes(m.group(5), "utf-8").decode("unicode_escape"))
        else:
            t = m.group(6)
            yield (("role", t[1:]) if t.startswith(":") and len(t) > 1 else ("atom", t))


def parse(s: str) -> Meaning:
    """Text -> meaning.  (assert :subj cat :rel is_a :obj animal)  [a b c]  word"""
    toks = list(_tokens(s))
    pos = 0

    def item():
        nonlocal pos
        t, val = toks[pos]; pos += 1
        if t == "atom":
            return val
        if t == "[":
            out = []
            while toks[pos][0] != "]":
                out.append(item())
            pos += 1
            return out
        if t == "(":
            fr: Dict[str, Any] = {}
            if toks[pos][0] == "atom":
                fr["act"] = toks[pos][1]; pos += 1
            while toks[pos][0] != ")":
                tt, r = toks[pos]; pos += 1
                if tt != "role":
                    raise SyntaxError(f"expected :role, got {r!r}")
                fr[r] = item()
            pos += 1
            return fr
        raise SyntaxError(f"unexpected {t}")

    m = item()
    if pos != len(toks):
        raise SyntaxError("trailing tokens")
    return m


def _atom_text(a: str) -> str:
    if a and re.fullmatch(r'[^\s()\[\]":][^\s()\[\]"]*', a):
        return a
    return '"' + a.replace("\\", "\\\\").replace('"', '\\"') + '"'


def show(m: Meaning) -> str:
    """Meaning -> text (inverse of parse)."""
    if m is None:
        return "<unreadable>"
    if isinstance(m, str):
        return _atom_text(m)
    if isinstance(m, (list, tuple)):
        return "[" + " ".join(show(x) for x in m) + "]"
    parts = []
    head = m.get("act")
    if isinstance(head, str):
        parts.append(_atom_text(head))
    for r, f in m.items():
        if r == "act" and isinstance(head, str):
            continue
        parts.append(f":{r} {show(f)}")
    return "(" + " ".join(parts) + ")"


# ---------------------------------------------------------------- one-liners for the channel
def say(text_or_meaning: Union[str, Meaning], lex: Optional[Lexicon] = None) -> Tuple[str, np.ndarray]:
    """-> (surface text, wire payload). Use: post(me, to, *say("(ask :subj x :rel is_a :obj ?)"))."""
    m = parse(text_or_meaning) if isinstance(text_or_meaning, str) and text_or_meaning.lstrip()[:1] in "([" \
        else text_or_meaning
    return show(m), to_wire(encode(m, lex))


def hear(payload: np.ndarray, lex: Optional[Lexicon] = None) -> Reading:
    """Wire payload -> Reading. Reloads the vocab file first so new words are known."""
    lex = lex or default_lexicon()
    lex.reload()
    return read_back(payload, lex)
