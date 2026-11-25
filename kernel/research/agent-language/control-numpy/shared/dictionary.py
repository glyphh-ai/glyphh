"""dictionary.py: the language grows (owner: lexicon).  numpy + stdlib only.

A DEFINITION gives a new word a meaning made of old words:
    (define :name isa_chain :def (rule :cond [(fact :subj ?x :rel is_a :obj ?y)
                                               (fact :subj ?y :rel is_a :obj ?z)]
                                        :then (fact :subj ?x :rel is_a :obj ?z)))
Definitions live in shared/dictionary.jsonl (append-only, flock); the new word is
registered in shared/vocab.txt so every reader can decode it.

What the dictionary does:
  compress(m)   replace every sub-structure that equals a definition with its word
                (shorter messages: fewer leaves, so more fits under language.max_leaves)
  expand(m)     the inverse: replace defined words by their definitions (recursive)
  mine(corpus)  find sub-structures that recur in real traffic and propose them as
                new words, ranked by leaves saved; adopt() defines them
  sense(word)   a defined word's vector = encode(its expansion), so concepts built from
                shared parts are SIMILAR (atoms alone are random and unrelated)
  recognise(v)  which defined concepts a vector resembles (nearest by sense)

    import dictionary as Dn
    dic = Dn.Dictionary()
    dic.define("lexicon", "isa_chain", Dn.L.parse("(rule ...)"))
    short = dic.compress(meaning); assert dic.expand(short) == meaning
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

import language as L

DICT_FILE = L.SHARED / "dictionary.jsonl"


def key(m: L.Meaning) -> str:
    """Canonical text of a meaning; frames are order-free, so sort their roles."""
    if isinstance(m, str):
        return L._atom_text(m)
    if isinstance(m, np.ndarray):
        return "#vec" + hashlib.sha256(m.tobytes()).hexdigest()[:8]
    if isinstance(m, (list, tuple)):
        return "[" + " ".join(key(x) for x in m) + "]"
    return "(" + " ".join(f":{r.lower()} {key(f)}" for r, f in sorted(m.items(), key=lambda t: t[0].lower())) + ")"


def subterms(m: L.Meaning):
    """Every frame/list inside m (including m), outermost first."""
    if isinstance(m, dict):
        yield m
        for f in m.values():
            yield from subterms(f)
    elif isinstance(m, (list, tuple)):
        yield m
        for f in m:
            yield from subterms(f)


class Dictionary:
    def __init__(self, path: Optional[Path] = DICT_FILE, lex: Optional[L.Lexicon] = None):
        self.path = Path(path) if path else None
        self.lex = lex or L.default_lexicon()
        self.entries: Dict[str, Dict[str, Any]] = {}     # word -> {def, by, ts}
        self._idx: Optional[Dict[str, str]] = None       # key(expanded def) -> word
        self._seen_lines = 0
        self.reload()

    # ------------------------------------------------------------ storage
    def reload(self) -> "Dictionary":
        if self.path and self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            for line in lines[self._seen_lines:]:
                if line.strip():
                    e = json.loads(line)
                    self._add(e["name"], L.parse(e["def"]), e.get("by", "?"), e.get("ts", 0))
            self._seen_lines = len(lines)
        return self

    @property
    def _by_key(self) -> Dict[str, str]:
        """Index of definitions by their FULLY EXPANDED canonical text, so a structure
        is recognised whether it is spelled with defined words or without."""
        if self._idx is None:
            self._idx = {}
            for n, e in self.entries.items():
                self._idx.setdefault(key(self.expand(e["def"])), n)
        return self._idx

    def _add(self, name, meaning, by, ts):
        if name in self.entries or key(self.expand(meaning)) in self._by_key:
            return False
        self.entries[name] = {"def": meaning, "by": by, "ts": ts}
        self._idx = None
        return True

    def define(self, by: str, name: str, meaning: L.Meaning, persist: bool = True,
               allow_existing: bool = False) -> L.Meaning:
        """Add a word. Returns the (define ...) meaning to send on the channel.
        Refuses redefinition (a word keeps its first meaning) and duplicate definitions."""
        self.reload()
        if isinstance(meaning, str) or isinstance(meaning, np.ndarray):
            raise ValueError("define a structure, not an atom")
        if name in self.entries:
            if key(self.expand(self.entries[name]["def"])) == key(self.expand(meaning)):
                return {"act": "define", "name": name, "def": meaning}
            raise ValueError(f"{name!r} is already defined differently")
        if key(self.expand(meaning)) in self._by_key:
            raise ValueError(f"already defined as {self._by_key[key(self.expand(meaning))]!r}")
        if not allow_existing and name in self.lex.reload():
            # a word already in use (e.g. a file name in facts) must not silently change
            # meaning everywhere it appears: expand() would rewrite every old sentence
            raise ValueError(f"{name!r} is already a word in use; pick a fresh name")
        ts = time.time()
        self._add(name, meaning, by, ts)
        self.lex.learn([name] + L.words_of(meaning)[0], L.words_of(meaning)[1], persist=persist)
        if persist and self.path:
            with self.path.open("a", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps({"name": name, "def": L.show(meaning), "by": by, "ts": ts}) + "\n")
                fcntl.flock(f, fcntl.LOCK_UN)
            self._seen_lines += 1
        return {"act": "define", "name": name, "def": meaning}

    def learn_from(self, m: L.Meaning, by: str = "?", persist: bool = True,
                   in_use: Iterable[str] = ()) -> Optional[str]:
        """Adopt a (define :name X :def ...) meaning heard on the channel. A hearer can only
        decode the name if it is already in vocab.txt (the definer put it there), so the
        freshness rule is enforced by the SPEAKER's define(); pass in_use= words seen used
        as plain words elsewhere to refuse a definition that would rewrite them."""
        if isinstance(m, dict) and m.get("act") == "define" and isinstance(m.get("name"), str) and "def" in m:
            if m["name"] in set(in_use):
                return None
            try:
                self.define(by, m["name"], L.canonical(m["def"]), persist=persist, allow_existing=True)
                return m["name"]
            except ValueError:
                return None
        return None

    def __contains__(self, w):
        return w in self.entries

    def __len__(self):
        return len(self.entries)

    # ------------------------------------------------------------ rewriting
    def expand(self, m: L.Meaning, max_depth: int = 8) -> L.Meaning:
        """Replace defined words by their definitions, recursively (definitions may use
        other defined words). Role names and non-defined words are left as they are."""
        if max_depth < 0:
            raise RecursionError("definition cycle")
        if isinstance(m, str):
            e = self.entries.get(m)
            return self.expand(e["def"], max_depth - 1) if e else m
        if isinstance(m, np.ndarray):
            return m
        if isinstance(m, (list, tuple)):
            return [self.expand(x, max_depth) for x in m]
        return {r: self.expand(f, max_depth) for r, f in m.items()}

    def compress(self, m: L.Meaning) -> L.Meaning:
        """Replace the LARGEST sub-structures that equal a definition (after expanding
        known words) by the defined word. expand(compress(m)) == expand(m)."""
        if isinstance(m, (str, np.ndarray)):
            return m
        hit = self._by_key.get(key(self.expand(m)))
        if hit is not None:
            return hit
        if isinstance(m, (list, tuple)):
            return [self.compress(x) for x in m]
        return {r: self.compress(f) for r, f in m.items()}

    # ------------------------------------------------------------ growth
    def mine(self, corpus: Iterable[L.Meaning], min_count: int = 2, min_leaves: int = 4,
             top: int = 10) -> List[Tuple[int, int, L.Meaning]]:
        """Sub-structures recurring in a corpus -> [(leaves_saved, count, meaning)], best first.
        Saving per use = leaf_count(sub) - 1 (the sub-structure becomes one word)."""
        cnt: Counter = Counter()
        rep: Dict[str, L.Meaning] = {}
        for m in corpus:
            seen = set()
            for s in subterms(self.expand(m)):
                if any(isinstance(x, np.ndarray) for x in (s.values() if isinstance(s, dict) else s)):
                    continue
                k = key(s)
                if k in self._by_key or k in seen:
                    continue
                seen.add(k)                      # count documents, not repeats inside one
                cnt[k] += 1; rep[k] = s
        out = []
        for k, c in cnt.items():
            n = L.leaf_count(rep[k])
            if c >= min_count and n >= min_leaves:
                out.append(((n - 1) * c, c, rep[k]))
        out.sort(key=lambda t: (-t[0], key(t[2])))
        # drop candidates that are strictly inside a better one with the same count
        kept: List[Tuple[int, int, L.Meaning]] = []
        for sv, c, s in out:
            ks = key(s)
            if any(c == c2 and ks in key(s2) for _, c2, s2 in kept):
                continue
            kept.append((sv, c, s))
        return kept[:top]

    @staticmethod
    def auto_name(m: L.Meaning) -> str:
        """A readable default name: head/rel words + a short hash."""
        parts = []
        if isinstance(m, dict):
            for r in ("act", "rel", "attr"):
                if isinstance(m.get(r), str):
                    parts.append(m[r])
        return "_".join(parts[:2] + ["c" + hashlib.sha256(key(m).encode()).hexdigest()[:6]])

    def adopt(self, by: str, candidates, persist: bool = True) -> List[L.Meaning]:
        """Define every mined candidate under an auto name; returns the (define ...) meanings."""
        out = []
        for _, _, s in candidates:
            if key(self.expand(s)) in self._by_key:
                continue
            out.append(self.define(by, self.auto_name(s), s, persist=persist))
        return out

    # ------------------------------------------------------------ meaning of words
    def sense(self, word: str) -> np.ndarray:
        """Vector for a word: its expanded definition if defined, else its atom."""
        return L.encode(self.expand(word), self.lex, persist=False) if word in self.entries \
            else L.atom(word, self.lex.dim)

    def recognise(self, v: np.ndarray, k: int = 3) -> List[Tuple[str, float]]:
        """Nearest defined concepts to a vector (by sense)."""
        if not self.entries:
            return []
        names = list(self.entries)
        M = np.stack([self.sense(n) for n in names]).astype(np.float32)
        s = M @ np.asarray(v, dtype=np.float32) / self.lex.dim
        idx = np.argsort(-s)[:k]
        return [(names[i], float(s[i])) for i in idx]
