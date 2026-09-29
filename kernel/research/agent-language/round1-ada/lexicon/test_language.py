"""Tests for shared/language.py.   python3 -m unittest agents/lexicon/test_language.py"""

import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))
from language import (HOLE, Lexicon, bind, from_b64, holes, render,  # noqa
                      roll, sim, symbol, to_b64)
from glyphh_kernel import Space  # noqa: E402


def private(**kw):
    return Lexicon(path=None, **kw)


class Vocabulary(unittest.TestCase):
    def test_words_and_roles_are_kernel_symbols(self):
        lx = private()
        self.assertTrue((lx.word("x") == symbol("val:x")).all())
        self.assertTrue((lx.role("r") == symbol("attr:r")).all())

    def test_flat_frame_is_space_situation(self):
        lx = private()
        for f in [{"subject": "bundle", "relation": "capacity"},
                  {"a": "1", "b": "2", "c": "3", "d": "4"},
                  {"only": "one"}]:
            self.assertTrue((lx.encode(f) == Space().encode(f)).all(), f)

    def test_deterministic_across_instances(self):
        m = {"act": "tell", "content": {"s": "a", "o": ["x", "y"]}}
        self.assertTrue((private().encode(m) == private().encode(m)).all())


class Grammar(unittest.TestCase):
    def setUp(self):
        self.lx = private()

    def roundtrip(self, m, **kw):
        return self.lx.decode(self.lx.encode(m), **kw)

    def test_word(self):
        self.lx.word("hello")
        self.assertEqual(self.roundtrip("hello"), "hello")

    def test_flat_frame(self):
        f = {"subject": "bundle", "relation": "capacity", "object": "32"}
        self.assertEqual(self.roundtrip(f), f)

    def test_nested_message(self):
        m = {"act": "tell", "from": "lexicon", "topic": "capacity",
             "content": {"subject": "bundle", "relation": "capacity",
                         "object": "32"}}
        self.assertEqual(self.roundtrip(m), m)

    def test_list_and_list_of_frames(self):
        self.assertEqual(self.roundtrip(["a", "b", "c"]), ["a", "b", "c"])
        m = {"a": "x", "steps": ["p", "q", {"k": "v", "j": "w"}]}
        self.assertEqual(self.roundtrip(m), m)

    def test_nesting_is_ordered(self):
        """bind is commutative; the roll on composite fillers must keep
        path (A,B) distinct from (B,A)."""
        a = self.lx.encode({"A": {"B": "w", "C": "v"}})
        b = self.lx.encode({"B": {"A": "w", "C": "v"}})
        self.assertLess(abs(sim(a, b)), 0.1)
        self.assertEqual(self.lx.decode(a), {"A": {"B": "w", "C": "v"}})

    def test_similarity_tracks_shared_slots(self):
        base = {f"r{i}": f"w{i}" for i in range(6)}
        other = dict(base, r0="z0", r1="z1", r2="z2")   # 3 of 6 shared
        s = self.lx.similar(base, other)
        self.assertTrue(0.25 < s < 0.45, s)
        self.assertLess(abs(self.lx.similar(base, {"q": "unrelated"})), 0.06)

    def test_bool_and_numbers_become_words(self):
        self.assertEqual(self.roundtrip({"ok": True, "n": 3}),
                         {"ok": "true", "n": "3"})

    def test_empty_frame_rejected(self):
        with self.assertRaises(ValueError):
            self.lx.encode({})


class Reading(unittest.TestCase):
    def test_random_glyph_reads_as_nothing(self):
        lx = private()
        for i in range(200):
            lx.word(f"w{i}")
        rng = np.random.RandomState(0)
        for _ in range(30):
            g = (rng.randint(0, 2, lx.dim) * 2 - 1).astype(np.int8)
            self.assertEqual(lx.parse(g), [])
            self.assertIsNone(lx.decode(g))

    def test_foreign_seed_reads_as_nothing(self):
        mine, theirs = private(), Lexicon(path=None, seed=7)
        f = {"subject": "a", "relation": "b", "object": "c"}
        mine.encode(f)
        self.assertEqual(mine.parse(theirs.encode(f)), [])

    def test_probe_and_cleanup(self):
        lx = private()
        g = lx.encode({"subject": "bundle", "object": "32"})
        self.assertEqual(lx.probe(g, "subject")[0][0], "bundle")
        self.assertEqual(lx.cleanup(bind(g, lx.role("object")))[0][0], "32")

    def test_capacity_32_slots_exact(self):
        lx = private()
        rng = random.Random(0)
        words = [f"w{i}" for i in range(500)]
        for w in words:
            lx.word(w)
        for _ in range(5):
            f = {f"r{i}": rng.choice(words) for i in range(32)}
            self.assertEqual(lx.decode(lx.encode(f), depth=0), f)

    def test_adaptive_threshold_grows_with_codebook(self):
        lx = private()
        t0 = lx.thr()
        for i in range(2000):
            lx.word(f"w{i}")
        self.assertGreater(lx.thr(), t0)
        self.assertEqual(private(threshold=0.2).thr(), 0.2)


class LearnedTypes(unittest.TestCase):
    """Selectional preferences: reading improves with use."""

    def setup(self, n_words=3000, n_roles=60, per_role=20, seen=300):
        rng = random.Random(3)
        lx = private()
        words = [f"w{i}" for i in range(n_words)]
        for w in words:
            lx.word(w)
        roles = [f"r{i}" for i in range(n_roles)]
        for r in roles:
            lx.role(r)
        vocab = {r: rng.sample(words, per_role) for r in roles}
        frame = lambda k: {r: rng.choice(vocab[r]) for r in rng.sample(roles, k)}
        for _ in range(seen):
            lx.encode(frame(8))
        return lx, frame

    def test_selections_are_learned_and_shared(self):
        with tempfile.TemporaryDirectory() as d:
            a = Lexicon(path=Path(d) / "cb", author="a")
            b = Lexicon(path=Path(d) / "cb", author="b")
            a.encode({"act": "tell", "subject": "zebra"})
            b.refresh()
            self.assertIn("zebra", b.selections["subject"])
            self.assertEqual(b.novel({"subject": "zebra", "object": "q"}),
                             [("object", "q")])

    def test_typed_reading_beats_untyped_on_big_frames(self):
        lx, frame = self.setup()
        speaker = private()                  # does not teach the reader
        tests = [frame(44) for _ in range(12)]
        glyphs = [speaker.encode(f) for f in tests]
        score = {}
        for typed in (False, True):
            lx.typed = typed
            score[typed] = sum(lx.decode(g, depth=0) == f
                               for f, g in zip(tests, glyphs))
        self.assertGreater(score[True], score[False])

    def test_typed_reading_adds_no_noise(self):
        lx, _ = self.setup()
        rng = np.random.RandomState(1)
        for _ in range(30):
            g = (rng.randint(0, 2, lx.dim) * 2 - 1).astype(np.int8)
            self.assertEqual(lx.parse(g, depth=0), [])


class Concepts(unittest.TestCase):
    def test_define_and_expand(self):
        lx = private()
        fact = {"subject": "bundle", "relation": "capacity", "object": "32"}
        lx.define("cap_fact", fact)
        m = {"act": "tell", "content": {"reason": "cap_fact", "kind": "x"}}
        self.assertEqual(lx.decode(lx.encode(m)), m)
        self.assertEqual(lx.decode(lx.encode(m), expand=True)["content"]
                         ["reason"], fact)

    def test_concepts_are_immutable(self):
        lx = private()
        lx.define("c", {"a": "b"})
        lx.define("c", {"a": "b"})          # same: fine
        with self.assertRaises(ValueError):
            lx.define("c", {"a": "z"})

    def test_chunk_does_not_change_the_glyph_and_reads_deep(self):
        lx = private()
        deep = {"a": "1", "b": "2",
                "n": {"a": "3", "b": "4",
                      "n": {"a": "5", "b": "6",
                            "n": {"a": "7", "b": "8",
                                  "n": {"a": "9", "b": "10"}}}}}
        raw = lx.encode(deep)
        self.assertNotEqual(lx.decode(raw), deep)       # depth 4: lost
        top = lx.chunk(deep)
        self.assertTrue((lx.encode(top) == raw).all())   # same glyph
        self.assertEqual(lx.decode(raw, expand=True), deep)

    def test_chunk_whole_rescues_big_content_in_an_envelope(self):
        rng = random.Random(5)
        content = {f"r{i}": f"w{rng.randint(0, 300)}" for i in range(12)}
        env = {"proto": "proto_v1", "from": "a", "to": "all", "act": "tell",
               "content": content, "topic": "t", "when": "now"}
        reader = private()
        reader.typed = False
        for i in range(301):
            reader.word(f"w{i}")
        reader.encode(content)                       # knows the roles
        g = private().encode(env)
        self.assertNotEqual(reader.decode(g).get("content"), content)
        reader.chunk(content, whole=True)            # now it is a concept
        self.assertEqual(reader.decode(g, expand=True)["content"], content)

    def test_concept_sharing_slots_does_not_steal_the_reading(self):
        """courier's live-audit bug: a known concept sharing 2 of 3 slots
        with the real content won the cleanup of the content slot (it
        does, 20/20, sim above thr). The fidelity check reads the slot
        anonymously too and keeps the reading that explains it better."""
        lx = private()
        lx.define("K", {"subject": "sandwich", "relation": "reliability",
                        "object": "high"})
        for i in range(10):
            c = {"subject": "sandwich", "relation": "reliability",
                 "object": f"v{i}"}
            g = lx.encode({"proto": "proto_v1", "from": "reasoner",
                           "to": "all", "act": "tell", "content": c})
            self.assertEqual(lx.probe(g, "content", 1)[0][0], "K")
            self.assertEqual(lx.decode(g)["content"], c)
        g = lx.encode({"act": "tell", "content": "K"})     # the real K
        self.assertEqual(lx.decode(g)["content"], "K")

    def test_atomic_concept(self):
        lx = private()
        g = lx.define("ptr", {"a": "b"}, atomic=True)
        self.assertLess(abs(sim(g, lx.encode({"a": "b"}))), 0.06)
        self.assertEqual(lx.decode(lx.encode({"x": "ptr"})), {"x": "ptr"})


class Questions(unittest.TestCase):
    def test_ask_and_holes(self):
        lx = private()
        q = lx.ask("object", subject="bundle", relation="capacity")
        self.assertEqual(q["object"], HOLE)
        self.assertEqual(holes(q), [("object",)])
        self.assertEqual(lx.decode(lx.encode(q)), q)
        self.assertEqual(holes({"a": ["x", {"b": HOLE}]}),
                         [("a", "#2", "b")])
        self.assertIn("want=object", render(q))


class SharedCodebook(unittest.TestCase):
    def test_receiver_learns_senders_words(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "cb.jsonl"
            alice = Lexicon(path=path, author="alice")
            bob = Lexicon(path=path, author="bob")
            m = {"act": "tell", "content": {"subject": "zebra_crossing",
                                            "object": "novel_word"}}
            g = alice.encode(m)
            alice.chunk({"deep": {"x": "y"}})
            self.assertEqual(bob.decode(g), m)          # refresh() inside
            self.assertIn("content", bob.nest_roles)
            self.assertTrue(any(n.startswith("c:") for n in bob.concepts))
            lines = [json.loads(l) for l in path.read_text().splitlines()]
            self.assertTrue(all(l["by"] == "alice" for l in lines))

    def test_b64_roundtrip(self):
        g = private().encode({"a": "b"})
        self.assertTrue((from_b64(to_b64(g)) == g).all())


if __name__ == "__main__":
    unittest.main()
