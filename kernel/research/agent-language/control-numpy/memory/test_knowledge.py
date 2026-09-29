"""Tests for shared/knowledge.py. All use a private lexicon + temp log, so the
shared vocab and shared/kb.jsonl are never touched.
Run: python3 -m unittest memory/test_knowledge.py  (from control-numpy/)"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "memory"))
import knowledge as K  # noqa: E402
import language as L  # noqa: E402


def fresh():
    d = Path(tempfile.mkdtemp())
    lex = L.Lexicon(path=None)
    return K.KB(d / "kb.jsonl", lex=lex), d / "kb.jsonl", lex


class TestTellGrade(unittest.TestCase):
    def test_log_carries_the_language(self):
        kb, path, lex = fresh()
        kb.tell("lexicon", "cat", "is_a", "animal")
        ev = json.loads(path.read_text().splitlines()[0])
        v = K._unb64(ev["wire"])
        self.assertEqual(v.shape, (L.D,))
        self.assertEqual(L.decode(v, lex), {"act": "assert", "subj": "cat",
                                            "rel": "is_a", "obj": "animal"})
        self.assertEqual(ev["text"], "(assert :subj cat :rel is_a :obj animal)")

    def test_ungraded_fact_is_uncertain(self):
        kb, _, _ = fresh()
        kb.tell("lexicon", "cat", "is_a", "animal")
        a = kb.ask("cat", "is_a")
        self.assertEqual(a.status, "uncertain")
        self.assertIsNone(a.obj)

    def test_self_grade_rejected(self):
        kb, _, _ = fresh()
        fid = kb.tell("lexicon", "cat", "is_a", "animal")
        with self.assertRaises(ValueError):
            kb.grade("lexicon", fid, True)

    def test_outside_grade_makes_it_answerable(self):
        kb, _, _ = fresh()
        fid = kb.tell("lexicon", "cat", "is_a", "animal")
        kb.grade("courier", fid, True)
        a = kb.ask("cat", "is_a")
        self.assertEqual((a.obj, a.status), ("animal", "answered"))
        self.assertAlmostEqual(a.conf, 0.6)   # one fresh grader: weight 0.5

    def test_refuted_fact_not_used(self):
        kb, _, _ = fresh()
        bad = kb.tell("courier", "cat", "is_a", "fish")
        good = kb.tell("lexicon", "cat", "is_a", "animal")
        kb.grade("memory", bad, False)
        kb.grade("reasoner", bad, False)
        kb.grade("memory", good, True)
        self.assertEqual(kb.ask("cat", "is_a").obj, "animal")
        self.assertLess(kb.trust(bad), 0.5)

    def test_more_trusted_wins(self):
        kb, _, _ = fresh()
        a = kb.tell("courier", "x", "color", "red")
        b = kb.tell("lexicon", "x", "color", "blue")
        kb.grade("memory", a, True)
        for g in ("memory", "reasoner", "courier"):
            kb.grade(g, b, True)
        self.assertEqual(kb.ask("x", "color").obj, "blue")

    def test_independent_tell_is_confirmation(self):
        kb, _, _ = fresh()
        fid = kb.tell("lexicon", "sun", "is_a", "star")
        self.assertEqual(kb.ask("sun", "is_a").status, "uncertain")
        fid2 = kb.tell("reasoner", "sun", "is_a", "star")
        self.assertEqual(fid, fid2)
        self.assertEqual(kb.ask("sun", "is_a").obj, "star")

    def test_ask_all_multi_valued(self):
        kb, _, _ = fresh()
        for o in ("language.py", "protocol.py", "knowledge.py"):
            kb.grade("memory", kb.tell("reasoner", "talk.py", "depends_on", o), True)
        kb.tell("reasoner", "talk.py", "depends_on", "numpy_only")      # ungraded
        got = sorted(a.obj for a in kb.ask_all("talk.py", "depends_on"))
        self.assertEqual(got, ["knowledge.py", "language.py", "protocol.py"])

    def test_ask_does_not_confuse_subjects(self):
        kb, _, _ = fresh()
        for i in range(30):
            f = kb.tell("lexicon", f"s{i}", "r", f"o{i}")
            kb.grade("memory", f, True)
        for i in range(30):
            self.assertEqual(kb.ask(f"s{i}", "r").obj, f"o{i}")
        self.assertEqual(kb.ask("s99", "r").status, "uncertain")
        self.assertEqual(kb.ask("s1", "other_rel").status, "uncertain")


class TestReputation(unittest.TestCase):
    def test_contrarian_grader_loses_weight(self):
        kb, _, _ = fresh()
        for i in range(12):
            f = kb.tell("lexicon", f"s{i}", "r", f"o{i}")
            kb.grade("memory", f, True)
            kb.grade("reasoner", f, True)
            kb.grade("courier", f, False)       # always against the others
        self.assertLess(kb.reputation("courier"), 0.5)
        self.assertGreaterEqual(kb.reputation("memory"), 0.75)  # 1-1 ties are skipped
        self.assertEqual(kb.weight("courier"), 0.0)
        f = kb.tell("lexicon", "z", "r", "oz")
        kb.grade("courier", f, True)            # the liar's lone ok no longer suffices
        self.assertEqual(kb.ask("z", "r").status, "uncertain")
        kb.grade("memory", f, True)
        self.assertEqual(kb.ask("z", "r").obj, "oz")


class TestSharedLog(unittest.TestCase):
    def test_two_agents_share_one_log(self):
        kb1, path, lex = fresh()
        kb2 = K.KB(path, lex=lex)
        fid = kb1.tell("lexicon", "cat", "is_a", "animal")
        kb2.grade("courier", fid, True)       # kb2 replays kb1's tell first
        self.assertEqual(kb1.ask("cat", "is_a").obj, "animal")  # kb1 sees kb2's grade

    def test_replay_rebuilds_state(self):
        kb, path, lex = fresh()
        fid = kb.tell("lexicon", "cat", "is_a", "animal")
        kb.grade("courier", fid, True)
        kb.grade("memory", fid, False)
        again = K.KB(path, lex=lex)
        self.assertAlmostEqual(again.trust(fid), kb.trust(fid))
        self.assertEqual(again.stats()["decode_bad"], 0)

    def test_grade_is_a_nested_sentence(self):
        kb, path, lex = fresh()
        fid = kb.tell("lexicon", "cat", "is_a", "animal")
        kb.grade("courier", fid, True, how="reproduced")
        ev = json.loads(path.read_text().splitlines()[1])
        m = L.decode(K._unb64(ev["wire"]), lex)
        self.assertEqual(m["act"], "grade")
        self.assertEqual(m["content"]["subj"], "cat")
        self.assertEqual(m["obj"], "yes")


class TestChecksAndTrails(unittest.TestCase):
    def test_expr_check_reproduced(self):
        kb, _, _ = fresh()
        good = kb.tell("reasoner", "7x8", "equals", "56", check="expr:7*8 == 56")
        bad = kb.tell("courier", "7x9", "equals", "64", check="expr:7*9 == 64")
        self.assertTrue(kb.reproduce("memory", good))
        self.assertFalse(kb.reproduce("memory", bad))
        self.assertEqual(kb.ask("7x8", "equals").obj, "56")
        self.assertEqual(kb.ask("7x9", "equals").status, "uncertain")

    def test_expr_check_is_safe(self):
        self.assertIsNone(K._check_expr(None, "expr:__import__('os').system('x')"))

    def test_lang_check(self):
        kb, _, _ = fresh()
        fid = kb.tell("lexicon", "sexpr", "round_trips", "yes",
                      check="lang:(assert :subj cat :rel is_a :obj animal)")
        self.assertTrue(kb.reproduce("courier", fid))

    def test_kbcurve_check(self):
        self.assertTrue(K._check_kbcurve(None, "kbcurve:0:60:wrong:<=:0.0"))
        self.assertFalse(K._check_kbcurve(None, "kbcurve:0:60:correct:>:0.99"))

    def test_via_is_recorded_not_graded(self):
        kb, _, _ = fresh()
        fid = kb.tell("memory", "a", "b", "c", via="courier")
        self.assertEqual(kb.facts_[fid]["via"], "courier")
        self.assertEqual(kb.facts_[fid]["grades"], {})

    def test_self_reproduce_does_not_grade(self):
        kb, _, _ = fresh()
        fid = kb.tell("reasoner", "2+2", "equals", "4", check="expr:2+2==4")
        kb.reproduce("reasoner", fid)
        self.assertEqual(kb.facts_[fid]["grades"], {})

    def test_derived_fact_capped_by_premise(self):
        kb, _, _ = fresh()
        p1 = kb.tell("lexicon", "cat", "is_a", "mammal")
        p2 = kb.tell("lexicon", "mammal", "is_a", "animal")
        kb.grade("courier", p1, True)
        for g in ("courier", "memory", "reasoner"):
            kb.grade(g, p2, True)
        d = kb.tell("reasoner", "cat", "is_a", "animal", trail=[p1, p2])
        kb.grade("courier", d, True, how="checked_premises")
        self.assertAlmostEqual(kb.trust(d), kb.trust(p1))   # capped at weakest premise
        kb.grade("memory", d, True, how="reproduced")
        self.assertGreater(kb.trust(d), kb.trust(p1))       # now directly reproduced


class TestCite(unittest.TestCase):
    def test_cite_inside_a_sentence(self):
        kb, _, lex = fresh()
        a = kb.tell("lexicon", "cat", "is_a", "mammal")
        b = kb.tell("lexicon", "mammal", "is_a", "animal")
        m = {"act": "answer", "subj": "cat", "rel": "is_a", "obj": "animal",
             "because": [kb.cite(a), kb.cite(b)]}
        v = L.encode(m, lex, persist=False)
        got = [kb.resolve(L.unbind_role(v, "because", f"#{i}")) for i in range(2)]
        self.assertEqual(got, [a, b])
        self.assertIsNone(kb.resolve(L.atom("nothing")))


class TestIngest(unittest.TestCase):
    def test_ingest_payload_sentences(self):
        kb, _, lex = fresh()
        _, wire = L.say("(assert :subj moon :rel orbits :obj earth)", lex)
        fid = kb.ingest({"from": "lexicon", "payload": wire})
        self.assertIsNotNone(fid)
        g = K.grade_meaning("courier", "moon", "orbits", "earth", True, "observed")
        kb.ingest({"from": "courier", "payload": L.to_wire(L.encode(g, lex, persist=False))})
        self.assertEqual(kb.ask("moon", "orbits").obj, "earth")

    def test_ingest_envelope(self):
        kb, _, lex = fresh()
        env = {"act": "tell", "from": "lexicon", "to": "all", "check": "proto_v1",
               "content": {"act": "assert", "subj": "moon", "rel": "orbits", "obj": "earth"}}
        fid = kb.ingest({"from": "lexicon", "payload": L.to_wire(L.encode(env, lex, persist=False))})
        self.assertEqual(fid, K.fact_id("moon", "orbits", "earth"))

    def test_ingest_ignores_questions(self):
        kb, _, lex = fresh()
        _, wire = L.say("(ask :subj moon :rel orbits :obj ?)", lex)
        self.assertIsNone(kb.ingest({"from": "reasoner", "payload": wire}))


class TestLearningCurve(unittest.TestCase):
    def test_curve_improves_and_graded_beats_naive(self):
        import curve
        rows = curve.run(seed=1, steps=400, log_every=100)
        first, last = rows[0], rows[-1]
        self.assertGreater(last["correct"], first["correct"] + 0.3)
        self.assertLess(last["uncertain"], first["uncertain"] - 0.3)
        self.assertEqual(max(r["wrong"] for r in rows), 0.0)
        self.assertGreater(last["naive_wrong"], 0.0)


if __name__ == "__main__":
    unittest.main()
