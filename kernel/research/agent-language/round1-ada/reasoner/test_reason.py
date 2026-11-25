"""Tests for shared/reason.py. Run: python3 -m unittest reasoner/test_reason.py"""

import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))

import numpy as np  # noqa: E402

import reason as rz  # noqa: E402
from reason import (Candidates, Frames, R, W, abstract, analogy, bind,  # noqa: E402
                    bundle, chain, closure, conclude, descend, fact_glyph,
                    judge, premise, typical, answer_glyph, ask_glyph, claim_of)

COUNTRIES = [
    ("france", "capital", "paris"), ("france", "currency", "euro"),
    ("france", "language", "french"),
    ("mexico", "capital", "mexico_city"), ("mexico", "currency", "peso"),
    ("mexico", "language", "spanish"),
    ("japan", "capital", "tokyo"), ("japan", "currency", "yen"),
    ("japan", "language", "japanese"),
]


class TestJudge(unittest.TestCase):
    def test_clean_symbol_is_known(self):
        c = Candidates(["a", "b", "c"])
        v = judge(W("b"), c)
        self.assertTrue(v.known)
        self.assertEqual(v.answer, "b")

    def test_noise_is_unknown(self):
        c = Candidates([f"w{i}" for i in range(100)])
        v = judge(W("not_a_candidate"), c)
        self.assertFalse(v.known)
        self.assertIsNone(v.answer)
        self.assertLess(v.conf, 0.9)

    def test_known_answers_are_right_on_random_frames(self):
        rng = random.Random(0)
        vocab = [f"v{i}" for i in range(100)]
        cands = Candidates(vocab)
        wrong_known = 0
        for _ in range(150):
            n = rng.randint(1, 200)
            vals = [rng.choice(vocab) for _ in range(n)]
            g = bundle([bind(R(f"r{i}"), W(v)) for i, v in enumerate(vals)])
            j = rng.randrange(n)
            v = judge(bind(g, R(f"r{j}")), cands)
            if v.known and v.answer != vals[j]:
                wrong_known += 1
        self.assertLessEqual(wrong_known, 2)


class TestFrames(unittest.TestCase):
    def setUp(self):
        self.kb = Frames(COUNTRIES)

    def test_ask(self):
        self.assertEqual(self.kb.ask("japan", "currency").answer, "yen")

    def test_absent_role_is_unknown(self):
        self.assertFalse(self.kb.ask("japan", "anthem").known)

    def test_unknown_subject_is_unknown(self):
        self.assertFalse(self.kb.ask("atlantis", "capital").known)

    def test_relation_between(self):
        self.assertEqual(self.kb.relation_between("france", "euro").answer,
                         "currency")

    def test_frame_is_space_encoding(self):
        from glyphh_kernel import Space
        sp = Space()
        g = sp.encode({"capital": "paris", "currency": "euro",
                       "language": "french"})
        self.assertTrue(np.array_equal(g, self.kb.frame("france")))


class TestAnalogy(unittest.TestCase):
    def test_dollar_of_mexico_both_modes(self):
        kb = Frames(COUNTRIES)
        for mode in ("relational", "algebraic"):
            v = analogy(kb, "france", "euro", "mexico", mode)
            self.assertEqual(v.answer, "peso", mode)

    def test_no_relation_no_answer(self):
        kb = Frames(COUNTRIES)
        v = analogy(kb, "france", "yen", "mexico")  # yen is not france's
        self.assertFalse(v.known)


class TestChain(unittest.TestCase):
    def setUp(self):
        self.kb = Frames([
            ("alice", "manager", "bob"), ("bob", "manager", "carol"),
            ("carol", "city", "oslo"), ("oslo", "country", "norway"),
            ("alice", "city", "rome"),
        ])

    def test_three_hops(self):
        c = chain(self.kb, "alice", ["manager", "manager", "city", "country"])
        self.assertTrue(c.known)
        self.assertEqual(c.answer, "norway")
        self.assertEqual(c.path, ["alice", "bob", "carol", "oslo", "norway"])

    def test_gap_makes_chain_unknown(self):
        c = chain(self.kb, "alice", ["manager", "spouse", "city"])
        self.assertFalse(c.known)
        self.assertIsNone(c.answer)


class TestClosure(unittest.TestCase):
    def test_taxonomy(self):
        kb = Frames([("cat", "is_a", "mammal"), ("mammal", "is_a", "animal"),
                     ("animal", "is_a", "organism"), ("dog", "is_a", "mammal"),
                     ("cat", "color", "black")])
        got = {d.fact for d in closure(kb, "is_a")}
        self.assertEqual(got, {
            ("cat", "is_a", "animal"), ("cat", "is_a", "organism"),
            ("dog", "is_a", "animal"), ("dog", "is_a", "organism"),
            ("mammal", "is_a", "organism")})
        d = [x for x in closure(kb, "is_a") if x.fact == ("cat", "is_a", "organism")][0]
        self.assertEqual(d.depth, 3)
        self.assertEqual(len(d.premises), 3)
        self.assertGreaterEqual(d.conf, rz.KNOWN_AT)


class TestAbstraction(unittest.TestCase):
    def test_gist_survives_noise(self):
        rng = random.Random(1)
        vals = [f"x{i}" for i in range(30)]
        proto = {f"a{i}": rng.choice(vals) for i in range(6)}
        cases = []
        for _ in range(15):
            inst = {a: (v if rng.random() > 0.4 else rng.choice(vals))
                    for a, v in proto.items()}
            cases.append(bundle([bind(R(a), W(v)) for a, v in sorted(inst.items())]))
        g = abstract(cases)
        cands = Candidates(vals)
        for a, v in proto.items():
            self.assertEqual(typical(g, a, cands).best, v)


class TestComposition(unittest.TestCase):
    def test_conclude_is_a_sentence_of_the_language(self):
        from language import Lexicon
        L = Lexicon(path=None)
        p1, p2 = fact_glyph("a", "is", "b"), fact_glyph("b", "is", "c")
        c = fact_glyph("a", "is", "c")
        g = conclude(c, [p1, p2], "transitive", 0.95)
        h = L.encode({"claim": c, "because": [p1, p2], "rule": "transitive",
                      "confidence": "likely"})
        self.assertTrue(np.array_equal(g, h))

    def test_premise_and_claim_readback(self):
        facts = [fact_glyph(f"s{i}", "is", f"o{i}") for i in range(3)]
        mem = {f"f{i}": f for i, f in enumerate(facts)}
        g = conclude(facts[2], facts[:2], "r")
        cm = Candidates.of_glyphs(mem)
        self.assertEqual(judge(premise(g, 1), cm).answer, "f0")
        self.assertEqual(judge(premise(g, 2), cm).answer, "f1")
        self.assertEqual(judge(claim_of(g), cm).answer, "f2")

    def test_descend_deep(self):
        rng = random.Random(2)
        base = fact_glyph("root_subject", "is", "x")
        mem, g = {"base": base}, base
        for i in range(8):
            other = fact_glyph(f"o{i}", "is", f"p{i}")
            g = conclude(fact_glyph(f"c{i}", "so", f"d{i}"), [g, other], "mp")
            mem[f"c{i}"], mem[f"o{i}"] = g, other
        name, conf, trail = descend(g, [("because", "#1")] * 8, mem)
        self.assertEqual(name, "base")
        self.assertEqual(trail[:2], ["c6", "c5"])


class TestQuestions(unittest.TestCase):
    def test_question_glyph_roundtrip(self):
        kb = Frames(COUNTRIES)
        g, info = answer_glyph(ask_glyph("mexico", "capital"), kb)
        self.assertEqual(info["status"], "known")
        self.assertTrue(np.array_equal(g, fact_glyph("mexico", "capital", "mexico_city")))

    def test_question_without_answer(self):
        kb = Frames(COUNTRIES)
        g, info = answer_glyph(ask_glyph("mexico", "anthem"), kb)
        self.assertIsNone(g)


if __name__ == "__main__":
    unittest.main()
