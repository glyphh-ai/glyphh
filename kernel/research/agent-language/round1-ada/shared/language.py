"""The shared language: meanings <-> glyphs, on the Ada kernel.

Owner: lexicon. API is STABLE; changes are announced on the channel first.

    from language import LX                     # default Lexicon, shared codebook
    g = LX.encode({"act": "tell", "subject": "bundle",
                   "relation": "capacity", "object": "about_20"})
    LX.decode(g)       -> {"act": "tell", "subject": "bundle", ...}
    LX.probe(g, "subject") -> [("bundle", 0.44), ...]     # one slot
    LX.cleanup(noisy)  -> [("bundle", 0.31), ...]          # nearest names

VOCABULARY (words are glyphs)
    word(w)  = symbol("val:" + w)     role(r) = symbol("attr:" + r)
    seed 42, dim 4096 (kernel defaults). These are exactly the symbols
    Space.encode uses, so a FLAT frame encodes bit-identically to
    Space.encode(frame): every sentence is a Space situation and back.

GRAMMAR (meaning -> glyph)
    str         a word (or, if defined, a named concept -> its glyph)
    dict        a frame: bundle([bind(role(r), encode(v)) for r in sorted])
    list/tuple  a sequence: the frame {"#1": x0, "#2": x1, ...}
    ndarray     a raw glyph, passed through (treated as composite)
    Frames nest: a filler can be a frame, a list, or a concept. A
    COMPOSITE filler is rolled by 1 inside its slot,
    bind(role, roll(inner, 1)), because bind is commutative: without
    the roll, path (A, B) and path (B, A) would be the same glyph.
    Word fillers are not rolled, so flat frames stay Space-identical.

READING (glyph -> meaning)
    probe every known role at once (unbind), clean each result up against
    the codebook of fillers (words + concepts). A slot counts when the
    best match clears thr(): adaptive, (sqrt(2 ln N) + 1.25) sigma for
    N = roles x fillers (0.095 at 128 x 1000), so a random glyph reads as
    nothing. A slot with no filler hit is probed one level deeper for
    an anonymous nested frame (under roles known to take frames). A hit on a named concept is replaced by the
    concept's clean glyph and read again (cleanup memory), so chunked
    structures decode to any depth.

CODEBOOK
    shared/codebook.jsonl, append-only JSON lines:
    {"kind": "word"|"role"|"concept", "name": ..., "by": ..., ["meaning": ...]}
    Every word/role you encode is appended, so the receiver can read it.
    refresh() pulls lines other agents appended.
"""

from __future__ import annotations

import base64
import fcntl
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

_ADA = Path(__file__).resolve().parents[2] / "kernel_v1"
if str(_ADA) not in sys.path:
    sys.path.insert(0, str(_ADA))

from glyphh_kernel import (DIM, Strand, bind, bundle, roll, sim,  # noqa: E402
                           symbol)

SEED = 42
HOLE = "?"                      # the word that marks a question's gap
CODEBOOK = Path(__file__).resolve().parent / "codebook.jsonl"
SIGMA = 1.0 / np.sqrt(DIM)      # std of sim between random glyphs

# The core role inventory. Any other role name is allowed; it is learned
# (appended to the codebook) on first use.
CORE_ROLES = [
    # speech act / envelope
    "act", "from", "to", "topic", "reply_to", "content", "proto", "thread",
    "claim", "rule",
    # a statement (fact triple) and its qualifiers
    "subject", "relation", "object", "value", "polarity", "confidence",
    "evidence", "reason", "because", "when", "where", "how", "unit",
    # thought / plan structure
    "goal", "risk", "step", "result", "cause", "effect", "part", "kind",
    "instance", "means", "condition", "then", "else",
    # a question: which slot it wants filled
    "want",
]
CORE_WORDS = [HOLE, "none", "true", "false", "neg", "pos",
              "tell", "ask", "answer", "propose", "agree", "disagree", "ack",
              "define", "grade", "done"]

Meaning = Any   # str | dict | list | tuple | np.ndarray


def _pos(i: int) -> str:
    return f"#{i + 1}"


def _is_pos(role: str) -> bool:
    return role.startswith("#") and role[1:].isdigit()


class Lexicon:
    """A vocabulary (codebook) plus the grammar that composes it."""

    def __init__(self, seed: int = SEED, dim: int = DIM,
                 path: Optional[Path] = CODEBOOK, author: str = "anon",
                 threshold: Optional[float] = None, max_positions: int = 16):
        self.seed, self.dim, self.author = seed, dim, author
        self.threshold = threshold
        self.path = Path(path) if path else None
        self._offset = 0
        self._names: Dict[str, List[str]] = {"role": [], "filler": []}
        self._known: Dict[str, set] = {"role": set(), "word": set()}
        self.concepts: Dict[str, Dict[str, Any]] = {}
        self._concept_glyph: Dict[str, np.ndarray] = {}
        self._mats: Dict[str, Optional[np.ndarray]] = {"role": None,
                                                       "filler": None}
        self._pending: List[dict] = []
        # valency: roles that have ever held a composite filler. Only
        # these are scanned for anonymous nested frames (cost control:
        # a full scan is roles x roles x fillers).
        self.nest_roles: set = set()
        # selectional preferences: role -> fillers it has taken, learned
        # from every encode by every agent (shared via the codebook).
        # Reading tries a role's own vocabulary first, at a lower bar.
        self.selections: Dict[str, set] = {}
        self._sel_idx: Dict[str, np.ndarray] = {}
        self.typed = True
        self._learning = True
        for r in CORE_ROLES + [_pos(i) for i in range(max_positions)]:
            self._add("role", r, persist=False)
        for w in CORE_WORDS:
            self._add("word", w, persist=False)
        self.refresh()

    # ── vocabulary ─────────────────────────────────────────────────
    def word(self, w: str) -> np.ndarray:
        self._add("word", w)
        return symbol(f"val:{w}", self.seed, self.dim)

    def role(self, r: str) -> np.ndarray:
        self._add("role", r)
        return symbol(f"attr:{r}", self.seed, self.dim)

    def glyph_of(self, name: str) -> np.ndarray:
        """The glyph a name stands for: a concept's glyph, else a word."""
        if name in self._concept_glyph:
            return self._concept_glyph[name]
        return self.word(name)

    def _add(self, kind: str, name: str, persist: bool = True,
             meaning: Any = None, atomic: bool = False,
             role: Optional[str] = None) -> None:
        if kind == "sel":
            got = self.selections.setdefault(role, set())
            if name not in got:
                got.add(name)
                self._sel_idx.pop(role, None)
                if persist:
                    self._persist({"kind": "sel", "name": name, "role": role,
                                   "by": self.author})
            return
        if kind == "nest":
            if name not in self.nest_roles:
                self.nest_roles.add(name)
                if persist:
                    self._persist({"kind": "nest", "name": name,
                                   "by": self.author})
            return
        if kind == "concept":
            if name in self.concepts:
                return
            self.concepts[name] = {"meaning": meaning, "atomic": atomic}
            self._concept_glyph[name] = (
                symbol(f"concept:{name}", self.seed, self.dim) if atomic
                else self._encode(meaning))
            if name not in self._known["word"]:
                self._names["filler"].append(name)
                self._known["word"].add(name)
            self._mats["filler"] = None
            if persist:
                self._persist({"kind": "concept", "name": name,
                               "meaning": meaning, "atomic": atomic,
                               "by": self.author})
            return
        bucket = "role" if kind == "role" else "word"
        if name in self._known[bucket]:
            return
        self._known[bucket].add(name)
        self._names["role" if kind == "role" else "filler"].append(name)
        self._mats["role" if kind == "role" else "filler"] = None
        if persist:
            self._persist({"kind": kind, "name": name, "by": self.author})

    def _persist(self, entry: dict) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(entry) + "\n")
            fcntl.flock(f, fcntl.LOCK_UN)

    def refresh(self) -> int:
        """Pull codebook entries other agents appended. Returns count."""
        if self.path is None or not self.path.exists():
            return 0
        with self.path.open() as f:
            f.seek(self._offset)
            data = f.read()
        # only consume complete lines
        cut = data.rfind("\n") + 1
        self._offset += len(data[:cut].encode())
        n = 0
        for line in data[:cut].splitlines():
            if not line.strip():
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._add(e["kind"], e["name"], persist=False,
                      meaning=e.get("meaning"), atomic=e.get("atomic", False),
                      role=e.get("role"))
            n += 1
        return n

    @property
    def roles(self) -> List[str]:
        return list(self._names["role"])

    @property
    def fillers(self) -> List[str]:
        return list(self._names["filler"])

    def _matrix(self, kind: str) -> np.ndarray:
        if self._mats[kind] is None:
            if kind == "role":
                rows = [symbol(f"attr:{r}", self.seed, self.dim)
                        for r in self._names["role"]]
            else:
                # each filler as it sits in a slot (composites rolled)
                rows = [self._filler(n) if n in self._concept_glyph
                        else symbol(f"val:{n}", self.seed, self.dim)
                        for n in self._names["filler"]]
            self._mats[kind] = np.stack(rows).astype(np.float32)
        return self._mats[kind]

    # ── grammar: meaning -> glyph ──────────────────────────────────
    def encode(self, meaning: Meaning) -> np.ndarray:
        """Compose a meaning into one glyph (see module doc)."""
        return self._encode(meaning)

    def _encode(self, m: Meaning) -> np.ndarray:
        if isinstance(m, np.ndarray):
            return m.astype(np.int8)
        if isinstance(m, bool):
            m = "true" if m else "false"
        if isinstance(m, (int, float)):
            m = str(m)
        if isinstance(m, str):
            return self.glyph_of(m)
        if isinstance(m, (list, tuple)):
            m = {_pos(i): x for i, x in enumerate(m)}
        if isinstance(m, dict):
            if not m:
                raise ValueError("cannot encode an empty frame")
            for r, v in m.items():
                if not self._learning:
                    break
                if self._is_composite(v):
                    self._add("role", r)
                    self._add("nest", r)
                if isinstance(v, str) and not _is_pos(r):
                    self._add("role", r)
                    self._add("word", v)
                    self._add("sel", v, role=r)
            return bundle([bind(self.role(r), self._filler(v))
                           for r, v in sorted(m.items())])
        raise TypeError(f"not a meaning: {type(m).__name__}")

    def _quiet(self):
        """Context: encode without learning (no codebook writes)."""
        import contextlib

        @contextlib.contextmanager
        def cm():
            old, self._learning = self._learning, False
            try:
                yield
            finally:
                self._learning = old
        return cm()

    def _is_composite(self, m: Meaning) -> bool:
        if isinstance(m, (dict, list, tuple, np.ndarray)):
            return True
        c = self.concepts.get(m) if isinstance(m, str) else None
        return c is not None and not c["atomic"]

    def _filler(self, m: Meaning) -> np.ndarray:
        """A meaning as it sits in a slot. Composite fillers are rolled
        by 1 so nesting is ordered: bind is commutative, so without the
        roll bind(rA, bind(rB, w)) == bind(rB, bind(rA, w)) and the
        paths (A,B) and (B,A) would be the same glyph."""
        g = self._encode(m)
        return roll(g, 1) if self._is_composite(m) else g

    def define(self, name: str, meaning: Meaning,
               atomic: bool = False) -> np.ndarray:
        """Chunk a composite under a name (a concept). Afterwards the
        string `name` inside any meaning encodes as the concept's glyph,
        and reading cleans it up to `name` and can expand it again.
        atomic=True gives the concept a fresh random glyph (a pointer:
        perfect cleanup, no structural similarity); default is
        structural (the glyph IS the encoded meaning)."""
        if name in self.concepts:
            if self.concepts[name]["meaning"] != meaning:
                raise ValueError(f"concept {name!r} already defined "
                                 "differently; concepts are immutable")
            return self._concept_glyph[name]
        # learn the parts first so the definition is readable
        self._encode(meaning)
        self._add("concept", name, meaning=meaning, atomic=atomic)
        return self._concept_glyph[name]

    def chunk(self, meaning: Meaning, prefix: str = "c:",
              whole: bool = False) -> Meaning:
        """Chunk every nested composite, bottom-up, into a concept named
        by its content hash (prefix + 10 hex). Returns the top meaning
        with names in place of sub-frames. encode(chunk(m)) reads back
        at ANY depth (measured: 1.00 exact at depth 4, where anonymous
        nesting is 0.00), and decode(g, expand=True) restores m. The
        definitions go to the shared codebook, so receivers can read it.
        Same meaning -> same name, on every machine.
        whole=True also defines the top frame and returns its NAME: use it
        for content that rides inside an envelope (measured: 6-24 slot
        content inside a 7-part envelope reads 1.00 exact as a concept,
        0.00 anonymous)."""
        import hashlib

        def walk(m: Meaning, top: bool) -> Meaning:
            if isinstance(m, (list, tuple)):
                m = {_pos(i): x for i, x in enumerate(m)}
                was_list = True
            else:
                was_list = False
            if not isinstance(m, dict):
                return m
            inner = {k: walk(v, False) for k, v in m.items()}
            if was_list:
                inner = [inner[_pos(i)] for i in range(len(inner))]
            if top and not whole:
                return inner
            key = json.dumps(inner, sort_keys=True, default=str)
            name = prefix + hashlib.sha1(key.encode()).hexdigest()[:10]
            self.define(name, inner)
            return name

        return walk(meaning, True)

    def trail(self, meanings: Iterable[Meaning],
              decay: float = 0.7) -> np.ndarray:
        """An ordered, recency-weighted state (kernel Strand). Unlike a
        list, it is compared, not decoded: use it for trajectories."""
        return Strand([self._encode(x) for x in meanings]).state(decay)

    # ── reading: glyph -> meaning ──────────────────────────────────
    def cleanup(self, g: np.ndarray, top: int = 3,
                kind: str = "filler") -> List[Tuple[str, float]]:
        """Nearest codebook names to a (noisy) glyph."""
        s = self._matrix(kind) @ g.astype(np.float32) / self.dim
        idx = np.argsort(s)[::-1][:top]
        names = self._names[kind]
        return [(names[i], float(s[i])) for i in idx]

    def probe(self, g: np.ndarray, role: str,
              top: int = 3) -> List[Tuple[str, float]]:
        """Read one slot: unbind the role, clean up the filler."""
        return self.cleanup(bind(g, self.role(role)), top)

    def _slot_scores(self, g: np.ndarray) -> np.ndarray:
        """(roles x fillers) similarity of every unbound slot to every
        filler: one matmul."""
        R = self._matrix("role")
        F = self._matrix("filler")
        U = R * g.astype(np.float32)[None, :]
        return (U @ F.T) / self.dim

    def parse(self, g: np.ndarray, depth: int = 3,
              threshold: Optional[float] = None,
              scan_all: bool = False,
              _path: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...],
                                                         str, float]]:
        """Every slot found: [(role_path, filler_name, sim)]. Paths are
        tuples of roles from the top frame down. Nested frames are
        looked for under nest_roles only (roles that have held a
        composite in any encode, shared via the codebook); scan_all=True
        tries every role (slow: roles x roles x fillers)."""
        if not _path:
            self.refresh()
        thr = self.thr() if threshold is None else threshold
        roles, fillers = self._names["role"], self._names["filler"]
        out = []
        for ri, name, s in self._leaves(g, thr):
            path = _path + (roles[ri],)
            c = self.concepts.get(name)
            if c is not None and not c["atomic"] and depth > 0:
                # fidelity check: a structural concept that merely SHARES
                # a few slots with the real filler can win the cleanup
                # (courier's live audit: 5/17 misreads). Read the slot
                # anonymously too; keep whichever reading's re-encoding
                # explains the slot better.
                inner = roll(bind(g, self.role(roles[ri])), -1)
                anon = self.parse(inner, depth - 1, thr, scan_all, path)
                if len(anon) >= 2:
                    alt = _listify(_tree(anon, len(path)))
                    with self._quiet():
                        alt_g = self._encode(alt)
                    if sim(inner, alt_g) > sim(inner, self._concept_glyph[name]):
                        out.extend(anon)
                        continue
            out.append((path, name, s))
        if depth <= 0:
            return out
        found = {p[len(_path)] for p, _, _ in out}
        # anonymous nested frames: scan each empty slot one level down
        # (leaves only, one matmul per role), then recurse into the
        # slots that really hold a frame. Cost is linear in roles.
        for r in (roles if scan_all else sorted(self.nest_roles)):
            if r in found:
                continue
            inner = roll(bind(g, self.role(r)), -1)   # unroll: composite
            sub = self._leaves(inner, thr)
            # a nested frame needs 2+ slots, or one strong one, to count
            if len(sub) >= 2 or (sub and sub[0][2] >= 1.5 * thr):
                out.extend(self.parse(inner, depth - 1, thr, scan_all,
                                      _path + (r,)))
        return out

    def thr(self) -> float:
        """The reading threshold. Fixed if set; else adaptive: the
        expected max of noise over the whole roles x fillers table plus
        a margin, (sqrt(2 ln N) + 1.25) * sigma, floored at 0.08. A
        bigger codebook needs a higher bar (more chances for noise)."""
        if self.threshold is not None:
            return self.threshold
        n = max(2, len(self._names["role"]) * len(self._names["filler"]))
        return max(0.08, (np.sqrt(2 * np.log(n)) + 1.25) / np.sqrt(self.dim))

    def type_thr(self, role: str) -> float:
        """The lower bar for a role's own vocabulary (its selections):
        same formula as thr() with N = roles x |selections(role)|."""
        k = len(self.selections.get(role, ()))
        n = max(2, len(self._names["role"]) * max(k, 1))
        return max(0.06, (np.sqrt(2 * np.log(n)) + 1.25) / np.sqrt(self.dim))

    def _sel(self, role: str) -> Optional[np.ndarray]:
        if role not in self.selections:
            return None
        if role not in self._sel_idx:
            pos = {n: i for i, n in enumerate(self._names["filler"])}
            self._sel_idx[role] = np.array(
                [pos[n] for n in self.selections[role] if n in pos], int)
        return self._sel_idx[role]

    def _leaves(self, g: np.ndarray, thr: float) -> List[Tuple[int, str, float]]:
        S = self._slot_scores(g)
        best = S.argmax(axis=1)
        fillers, roles = self._names["filler"], self._names["role"]
        out = []
        for ri, fi in enumerate(best):
            s = float(S[ri, fi])
            if s >= thr:
                out.append((ri, fillers[fi], s))
                continue
            if not self.typed or self.threshold is not None:
                continue
            idx = self._sel(roles[ri])
            if idx is None or not len(idx):
                continue
            j = idx[int(S[ri, idx].argmax())]
            # typed hit: best in the role's vocabulary, AND the global
            # best (the same filler, or nothing better elsewhere)
            if S[ri, j] >= self.type_thr(roles[ri]) and j == fi:
                out.append((ri, fillers[j], float(S[ri, j])))
        return sorted(out, key=lambda t: -t[2])

    def novel(self, meaning: Meaning) -> List[Tuple[str, str]]:
        """(role, filler) pairs in a meaning's top frame that this role
        has never taken before: surprise, relative to the group's usage."""
        if not isinstance(meaning, dict):
            return []
        return [(r, v) for r, v in meaning.items()
                if isinstance(v, str) and not _is_pos(r)
                and v not in self.selections.get(r, ())]

    def decode(self, g: np.ndarray, depth: int = 3,
               threshold: Optional[float] = None,
               expand: bool = False, scan_all: bool = False) -> Meaning:
        """Read a glyph back into a meaning (dict / list / word).
        expand=True replaces named concepts by their definitions."""
        slots = self.parse(g, depth, threshold, scan_all)
        if not slots:
            # maybe the glyph is a bare word/concept
            thr = self.thr() if threshold is None else threshold
            name, s = max(self.cleanup(g, 1)[0],
                          self.cleanup(roll(g, 1), 1)[0], key=lambda t: t[1])
            return self._maybe_expand(name, expand) if s >= thr else None
        return _listify(self._maybe_expand(_tree(slots), expand))

    def _maybe_expand(self, name: Meaning, expand: bool) -> Meaning:
        if not expand:
            return name
        if isinstance(name, str) and name in self.concepts:
            return self._maybe_expand(self.concepts[name]["meaning"], True)
        if isinstance(name, dict):
            return {k: self._maybe_expand(v, True) for k, v in name.items()}
        if isinstance(name, list):
            return [self._maybe_expand(v, True) for v in name]
        return name

    # ── questions ──────────────────────────────────────────────────
    def ask(self, want: str, **known: Meaning) -> Dict[str, Any]:
        """A question meaning: the known slots, the wanted slot set to
        the hole '?', act=ask, want=<role>."""
        q = dict(known)
        q[want] = HOLE
        q["act"] = "ask"
        q["want"] = want
        return q

    # ── similarity / transport ─────────────────────────────────────
    def similar(self, a: Meaning, b: Meaning) -> float:
        return sim(self._encode(a), self._encode(b))


def _tree(slots, strip: int = 0) -> Dict[str, Any]:
    """Slots [(path, name, sim)] -> nested dict (paths minus `strip`)."""
    tree: Dict[str, Any] = {}
    for path, name, _ in slots:
        path = path[strip:]
        node = tree
        for r in path[:-1]:
            nxt = node.get(r)
            if not isinstance(nxt, dict):
                nxt = node[r] = {}
            node = nxt
        if path and path[-1] not in node:
            node[path[-1]] = name
    return tree


def _listify(m: Meaning) -> Meaning:
    """Turn frames whose roles are all positional into lists."""
    if isinstance(m, dict):
        m = {k: _listify(v) for k, v in m.items()}
        if m and all(_is_pos(k) for k in m):
            n = max(int(k[1:]) for k in m)
            return [m.get(_pos(i)) for i in range(n)]
    return m


def holes(meaning: Meaning, _path: Tuple[str, ...] = ()) -> List[Tuple[str, ...]]:
    """Paths of every '?' in a meaning."""
    if meaning == HOLE:
        return [_path]
    if isinstance(meaning, dict):
        return [p for k, v in meaning.items() for p in holes(v, _path + (k,))]
    if isinstance(meaning, (list, tuple)):
        return [p for i, v in enumerate(meaning)
                for p in holes(v, _path + (_pos(i),))]
    return []


def render(m: Meaning) -> str:
    """Compact human text for a meaning: act(role=filler, ...)."""
    if isinstance(m, dict):
        head = m.get("act", "")
        body = ", ".join(f"{k}={render(v)}" for k, v in sorted(m.items())
                         if k != "act")
        return f"{head}({body})"
    if isinstance(m, list):
        return "[" + ", ".join(render(x) for x in m) + "]"
    return str(m)


def to_b64(g: np.ndarray) -> str:
    return base64.b64encode(np.asarray(g, dtype=np.int8).tobytes()).decode()


def from_b64(s: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=np.int8).copy()


LX = Lexicon(author="shared")

__all__ = ["Lexicon", "LX", "HOLE", "SEED", "DIM", "SIGMA", "CORE_ROLES",
           "CORE_WORDS", "holes", "render", "to_b64", "from_b64",
           "bind", "bundle", "roll", "sim", "symbol", "Strand"]
