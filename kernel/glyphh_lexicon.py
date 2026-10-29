"""Ada's own reading: the English a text role reads with no language model in the path. Two seeds ship with the
kernel, in `lexicon/` beside this file (or `GLYPHH_LEXICON_DIR`):

  words.jsonl.gz    WordNet 3.0, 77,817 single words: each its synonyms, its near words (hypernyms, hyponyms,
                    similar-to, also-see, attributes, pertainyms, derivations) and its part of speech
  grammar.jsonl.gz  the Moby Part-of-Speech list, 192,960 word forms: each its parts of speech

A word's glyph is its own symbol tilted toward its neighbourhood: itself at 1.0, its synonyms sharing SYNONYMS,
its near words sharing NEAR, its classes sharing CLASSES, bundled by weight. So "arrive" and "come" correlate,
"stolen" leans toward "taken", and two nouns lean toward each other a little; a word the seeds do not know is its
symbol alone, as before. The kernel reads every item of a weighted set this way (a text role's bag, since the spec
emits one), nothing else: a category's value is never a word. Licences: lexicon/LICENSES.md."""

from __future__ import annotations

import gzip
import json
import math
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np

SYNONYMS = 0.9  # the voice a word's synonyms share in its glyph
NEAR = 0.6  # its near words'
CLASSES = 0.3  # its parts of speech'
CACHE = 50000  # word glyphs kept, per (seed, dim)
# a reach past 1 (Settings.word_reach, 3.16.0): each step out, a word's neighbours' neighbours join its glyph at
# STEP times the voice of the neighbour they came through, from the first BEAM neighbours of each (the seeds list a
# word's neighbours by its commonest senses first), so a reach stays a handful of words, never the dictionary
STEP = 0.5
BEAM = 6
LEMMA = 0.9  # the voice a word's plain form shares in its glyph ("charged" reads with "charge"), from reach 2
NEIGHBOURHOOD = 1.0  # from reach 2, the voice of the word's whole neighbourhood (its L2 norm) beside its own 1.0
# an inflected word's plain form, tried in order: the suffix taken off, then what is put back
_SUFFIXES = (
    ("ies", "y"), ("ied", "y"), ("ves", "f"), ("ves", "fe"), ("ses", "s"), ("xes", "x"), ("zes", "z"),
    ("ches", "ch"), ("shes", "sh"), ("men", "man"), ("ing", ""), ("ing", "e"), ("ed", ""), ("ed", "e"),
    ("er", ""), ("est", ""), ("es", ""), ("s", ""), ("ly", ""),
)
_IRREGULAR = {
    "stolen": "steal", "stole": "steal", "taken": "take", "took": "take", "gone": "go", "went": "go",
    "lost": "lose", "paid": "pay", "sent": "send", "made": "make", "got": "get", "gotten": "get",
    "bought": "buy", "sold": "sell", "brought": "bring", "came": "come", "done": "do", "did": "do",
    "said": "say", "told": "tell", "left": "leave", "kept": "keep", "found": "find", "given": "give",
    "gave": "give", "broke": "break", "broken": "break", "frozen": "freeze", "froze": "freeze",
    "spent": "spend", "seen": "see", "saw": "see", "known": "know", "knew": "know", "held": "hold",
    "won": "win", "felt": "feel", "meant": "mean", "began": "begin", "begun": "begin", "wrote": "write",
    "written": "write", "children": "child", "people": "person", "men": "man", "women": "woman",
}


def _folder() -> Path:
    """Where the seeds are: GLYPHH_LEXICON_DIR, else lexicon/ beside this file (a checkout, rrotor's Ada part),
    else the installed package's data (pip install glyphh-kernel puts lexicon/ there as glyphh_lexicon_data/)."""
    if os.environ.get("GLYPHH_LEXICON_DIR"):
        return Path(os.environ["GLYPHH_LEXICON_DIR"])
    here = Path(__file__).parent
    beside = here / "lexicon"
    if not beside.is_dir() and (here / "glyphh_lexicon_data").is_dir():
        return here / "glyphh_lexicon_data"
    return beside


class Lexicon:
    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder or _folder()
        # the whole process's off switch, for a caller that wants no lexicon anywhere. No model sets it: a model's
        # `lexicon` setting is its own (kernel.Space(lexicon=...)), so one process serves models with and without it.
        self.enabled = True
        self._words: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] | None = None
        self._grammar: dict[str, tuple[str, ...]] | None = None
        self._glyphs: OrderedDict[tuple[str, int, int], np.ndarray] = OrderedDict()
        self._available: tuple[Path, bool] | None = None

    @property
    def available(self) -> bool:
        """The seeds are there (looked for once per folder: every word's glyph asks)."""
        if self._available is None or self._available[0] != self.folder:
            found = (self.folder / "words.jsonl.gz").is_file() or (self.folder / "grammar.jsonl.gz").is_file()
            self._available = (self.folder, found)
        return self._available[1]

    def _load(self) -> None:
        if self._words is not None:
            return
        self._words, self._grammar = {}, {}
        path = self.folder / "words.jsonl.gz"
        if path.is_file():
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)["situation"]["word"]
                    m = r["meaning"]
                    self._words[r["identity"]["lemma"]] = (tuple(m.get("synonyms", ())), tuple(m.get("near", ())), m["pos"])
        path = self.folder / "grammar.jsonl.gz"
        if path.is_file():
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)["situation"]["word"]
                    self._grammar[r["identity"]["form"]] = tuple(r["grammar"]["pos"])

    def entry(self, word: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] | None:
        """A word's synonyms, near words and classes, or None when neither seed knows it."""
        self._load()
        assert self._words is not None and self._grammar is not None
        found = self._words.get(word)
        classes = self._grammar.get(word) or ((found[2],) if found else ())
        if found is None and not classes:
            return None
        return (found[0] if found else ()), (found[1] if found else ()), tuple(classes)

    def size(self) -> tuple[int, int]:
        self._load()
        assert self._words is not None and self._grammar is not None
        return len(self._words), len(self._grammar)

    def forget(self) -> None:
        self._glyphs.clear()

    def lemma(self, word: str) -> str | None:
        """An inflected word's plain form the word seed knows ("charged" -> "charge", "stolen" -> "steal"), or None
        when the word is a plain form already or none is found."""
        self._load()
        assert self._words is not None
        known = self._words.get(word)

        grammar = self._grammar if self._grammar is not None else {}

        def classes(w: str) -> set[str]:
            found = self._words.get(w) if self._words is not None else None
            return set(grammar.get(w, ())) | ({found[2]} if found else set())

        def tied(stem: str, suffix: str) -> bool:
            # a word the seed knows itself ("charged", "news") takes a plain form only as a derivation (the two
            # list each other), a verb form of a verb ("charged" from "charge") or a plural of a noun, so "news"
            # never reads as "new"
            if known is None:
                return True
            other = self._words.get(stem)
            if stem in known[0] or stem in known[1] or (other is not None and (word in other[0] or word in other[1])):
                return True
            if suffix in ("ed", "ied", "ing"):  # a verb form: the stem is a verb by either seed
                return any(c.endswith("verb") and c != "adverb" for c in classes(stem))
            if suffix in ("s", "es", "ies", "ses", "xes", "zes", "ches", "shes", "ves"):  # a plural: the stem is
                return other is not None and other[2] == "noun"  # first of all a noun ("cards"; never "news")
            return False

        if word in _IRREGULAR and _IRREGULAR[word] in self._words:
            return _IRREGULAR[word]
        for suffix, back in _SUFFIXES:
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                stem = word[: -len(suffix)] + back
                if stem != word and stem in self._words and tied(stem, suffix):
                    return stem
                if not back and len(stem) > 3 and stem[-1] == stem[-2] and stem[:-1] in self._words and tied(stem[:-1], suffix):
                    return stem[:-1]  # a doubled consonant: "stopped" -> "stop"
        return None

    def glyph(self, word: str, seed: int, dim: int, reach: int = 1) -> np.ndarray:
        """The word's glyph through the seeds (cached), or its bare symbol when off, absent or unknown. reach 1 is
        the word and its neighbours (synonyms, near words, classes); 2 and 3 (Settings.word_reach) add its plain
        form and that many steps of neighbours' neighbours."""
        from glyphh_kernel import bundle, symbol

        if not self.enabled or not self.available:
            return symbol(f"val:{word}", seed, dim)
        reach = max(1, min(3, int(reach)))
        key = (word, seed, dim) if reach == 1 else (word, seed, dim, reach)
        held = self._glyphs.get(key)
        if held is not None:
            self._glyphs.move_to_end(key)
            return held
        if reach == 1:
            made = self._near_glyph(word, seed, dim)
        else:
            voices = self._reach(word, reach)
            made = bundle([symbol(name, seed, dim) for name in voices], list(voices.values()))
        self._glyphs[key] = made
        if len(self._glyphs) > CACHE:
            self._glyphs.popitem(last=False)
        return made

    def _near_glyph(self, word: str, seed: int, dim: int) -> np.ndarray:
        """Reach 1: the word, its synonyms, its near words and its classes (the reading before 3.16.0)."""
        from glyphh_kernel import bundle, symbol

        entry = self.entry(word)
        own = symbol(f"val:{word}", seed, dim)
        if entry is None:
            return own
        synonyms, near, classes = entry
        parts, weights = [own], [1.0]
        for items, share, prefix in ((synonyms, SYNONYMS, "val"), (near, NEAR, "val"), (classes, CLASSES, "class")):
            for item in items:
                parts.append(symbol(f"{prefix}:{item}", seed, dim))
                weights.append(share / len(items))
        return bundle(parts, weights)

    def _reach(self, word: str, reach: int) -> dict[str, float]:
        """Reach 2 or 3: {symbol name: voice} of the word, its plain form, its classes and its neighbours out to
        `reach` steps. A neighbour met twice adds its voices (words that agree from two sides weigh more); each
        step takes the first BEAM neighbours of each word it starts from, at STEP of that word's voice."""
        own = {f"val:{word}": 1.0}
        frontier: dict[str, float] = {word: 1.0}
        plain = self.lemma(word)
        if plain is not None:
            own[f"val:{plain}"] = LEMMA
            frontier[plain] = LEMMA
        near_voices: dict[str, float] = {}
        seen = set(frontier)
        for step in range(reach):
            nxt: dict[str, float] = {}
            for w, voice in frontier.items():
                found = self.entry(w)
                if found is None:
                    continue
                for items, share in ((found[0], SYNONYMS), (found[1], NEAR)):
                    ranked = sorted(items, key=lambda i: (not self._mutual(w, i), i))  # the ones that list w back first
                    if step > 0:
                        ranked = ranked[:BEAM]
                    for item in ranked:
                        if item in seen:
                            continue
                        v = voice * (1.0 if step == 0 else STEP) * share * (2.0 if self._mutual(w, item) else 1.0)
                        near_voices[f"val:{item}"] = near_voices.get(f"val:{item}", 0.0) + v
                        nxt[item] = nxt.get(item, 0.0) + v
            seen |= set(nxt)
            # the next step starts from the loudest of this step's words only, so the reach stays small
            frontier = dict(sorted(nxt.items(), key=lambda kv: (-kv[1], kv[0]))[:BEAM])
        entry = self.entry(plain or word)
        classes = {f"class:{c}": CLASSES / len(entry[2]) for c in entry[2]} if entry is not None and entry[2] else {}
        # the neighbourhood speaks as one, as loud as the word itself: else forty neighbours at a fortieth each are
        # lost to the word's own symbol in the majority vote (the reading at reach 1, for a common word)
        norm = math.sqrt(sum(v * v for v in near_voices.values())) or 1.0
        return {**own, **classes, **{k: NEIGHBOURHOOD * v / norm for k, v in near_voices.items()}}

    def _mutual(self, a: str, b: str) -> bool:
        """b lists a among its synonyms or near words (and so the tie runs both ways)."""
        found = self._words.get(b) if self._words is not None else None
        return found is not None and (a in found[0] or a in found[1])

    def view(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "available": self.available, "folder": str(self.folder)}


LEXICON = Lexicon()
