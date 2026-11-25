"""Tests for shared/reason.py.  python3 -m unittest reasoner/test_reason.py -v
Private lexicons and temp KBs only: nothing lands in shared/vocab.txt or kb.jsonl."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "shared"))
sys.path.insert(0, str(HERE))

import language as L  # noqa: E402
import reason as R  # noqa: E402
import knowledge as K  # noqa: E402
import bench as B  # noqa: E402


def world():
    Rz = B.private()
    fm = R.FactMemory(Rz)
    for t in [("cat", "is_a", "mammal"), ("dog", "is_a", "mammal"), ("mammal", "is_a", "animal"),
              ("mammal", "has", "fur"), ("animal", "can", "breathe"), ("cat", "can", "purr"),
              ("paris", "capital_of", "france"), ("rome", "capital_of", "italy"),
              ("france", "located_in", "europe"), ("ann", "parent_of", "bob"),
              ("bob", "parent_of", "cy")]:
        fm.add(*t)
    return Rz, fm


class TestQuery(unittest.TestCase):
    def test_slot_read_and_absent_slot(self):
        Rz = B.private()
        v = Rz.encode({"act": "assert", "subj": "cat", "rel": "is_a", "obj": "animal"})
        self.assertEqual(Rz.query(v, "obj").value, "animal")
        self.assertEqual(Rz.query(v, "subj").value, "cat")
        self.assertFalse(Rz.query(v, "loc").known)          # no such slot -> unknown
        noise = L.atom("some random thing")
        self.assertFalse(Rz.query(noise, "obj").known)

    def test_nested_path(self):
        Rz = B.private()
        v = Rz.encode({"act": "answer", "content": {"subj": "x", "obj": "y"}})
        self.assertEqual(Rz.query(v, "content", "obj").value, "y")

    def test_calibration_heldout(self):
        r = B.bench_query(n=600, seed=11)
        self.assertLess(r["ece"], 0.05)
        self.assertGreater(r["acc_answered"], 0.97)


class TestAnalogy(unittest.TestCase):
    def test_dollar_of_mexico(self):
        Rz = B.private()
        usa = Rz.encode({"name": "usa", "loc": "washington", "val": "dollar"})
        mex = Rz.encode({"name": "mexico", "loc": "mexico_city", "val": "peso"})
        self.assertEqual(Rz.analogy(usa, mex, "dollar").value, "peso")
        self.assertEqual(Rz.analogy(usa, mex, "washington").value, "mexico_city")
        self.assertEqual(Rz.analogy_mapping(usa, mex, "dollar").value, "peso")
        self.assertFalse(Rz.analogy(usa, mex, "yen").known)

    def test_bench_analogy(self):
        r = B.bench_analogy(worlds=15)
        self.assertGreaterEqual(r["two_step_acc"], 0.98)
        self.assertGreaterEqual(r["abstain_on_absent"], 0.9)

    def test_fact_analogy(self):
        Rz, fm = world()
        self.assertEqual(Rz.analogy_facts(fm, "paris", "france", "rome").value, "italy")
        self.assertFalse(Rz.analogy_facts(fm, "paris", "france", "cat").known)
        self.assertFalse(Rz.analogy_facts(fm, "paris", "italy", "rome").known)


class TestAbstraction(unittest.TestCase):
    def test_gist_with_exceptions(self):
        r = B.bench_abstraction(trials=10)
        self.assertGreaterEqual(r["gist_precision"], 0.95)
        self.assertGreaterEqual(r["gist_recall"], 0.95)
        self.assertGreaterEqual(r["classify_acc"], 0.95)

    def test_entity_gist(self):
        Rz, fm = world()
        fm.infer(R.DEFAULT_RULES)
        _, common = fm.gist(["cat", "dog"])
        pairs = {(r, o) for r, o, _ in common}
        self.assertIn(("is_a", "mammal"), pairs)
        self.assertIn(("has", "fur"), pairs)
        self.assertNotIn(("can", "purr"), pairs)       # only the cat purrs


class TestInference(unittest.TestCase):
    def test_closure_exact(self):
        r = B.bench_inference(depth=3, branch=3)
        self.assertEqual(r["precision"], 1.0)
        self.assertEqual(r["recall"], 1.0)
        self.assertEqual(r["recheck_pass"], 1.0)
        self.assertGreaterEqual(r["explain_step_exact"], 0.99)

    def test_nested_conclusions_explain(self):
        Rz, fm = world()
        fm.infer(R.DEFAULT_RULES)
        f = fm.facts[R.fact_id("cat", "can", "breathe")]
        self.assertGreaterEqual(f.depth, 2)                 # a conclusion built on a conclusion
        tree = Rz.explain(fm, fm.vec(f.fid))
        self.assertEqual(tree["fact"], ("cat", "can", "breathe"))
        self.assertEqual(tree["rule"], "inherit_can")
        kids = [k["fact"] for k in tree["because"]]
        want = [(fm.facts[p].s, fm.facts[p].r, fm.facts[p].o) for p in f.premises]
        self.assertEqual(kids, want)                                  # decoded from the vector
        self.assertTrue(R.recheck(tree["fact"], tree["rule"], kids))
        self.assertTrue(any("rule" in k for k in tree["because"]))    # a premise is a conclusion

    def test_other_rules(self):
        Rz, fm = world()
        fm.infer(R.DEFAULT_RULES)
        self.assertEqual(fm.ask("cy", "child_of").value, "bob")
        self.assertEqual(fm.ask("ann", "grandparent_of").value, "cy")
        self.assertEqual(fm.ask("paris", "located_in").value, "europe")
        self.assertFalse(fm.ask("cat", "located_in").known)

    def test_contradictions(self):
        Rz, fm = world()
        fm.add("7x9", "equals", "63", conf=0.9)
        fm.add("7x9", "equals", "64", conf=0.3)
        pairs = [((a.s, a.o), (b.s, b.o)) for a, b in fm.contradictions()]
        self.assertEqual(pairs, [(("7x9", "63"), ("7x9", "64"))])

    def test_recheck(self):
        self.assertTrue(R.recheck(("a", "is_a", "c"), "transitive_is_a",
                                  [("a", "is_a", "b"), ("b", "is_a", "c")]))
        self.assertFalse(R.recheck(("a", "is_a", "d"), "transitive_is_a",
                                   [("a", "is_a", "b"), ("b", "is_a", "c")]))
        self.assertFalse(R.recheck(("a", "is_a", "c"), "transitive_is_a",
                                   [("a", "is_a", "b"), ("x", "is_a", "c")]))
        self.assertFalse(R.recheck(("a", "is_a", "c"), "no_such_rule", []))

    def test_growing_qa(self):
        r = B.bench_growing_qa(depth=3)
        self.assertEqual(r["coverage_before"], 0.0)
        self.assertEqual(r["acc_after"], 1.0)
        self.assertEqual(r["abstain_unanswerable_after"], 1.0)

    def test_learning_from_grades(self):
        r = B.bench_calibrated_inference(depth=3)
        self.assertLess(r["ece_derived_after_grades"], r["ece_derived_raw"])
        self.assertGreater(r["acc_answered_at_tau"], 0.9)


class TestLanguageForms(unittest.TestCase):
    def test_answer_meanings_round_trip(self):
        Rz, fm = world()
        fm.infer(R.DEFAULT_RULES)
        cases = {
            "(query :subj cat :rel has :obj ?)": "fur",
            "(query :rel analogy :subj [paris france rome] :obj ?)": "italy",
            "(query :subj cat :rel owns :obj ?)": "unknown",
        }
        for q, want in cases.items():
            a = fm.answer(L.parse(q))
            back = L.decode(L.encode(a, Rz.lex, persist=False), Rz.lex)
            self.assertEqual(back["obj"], want, q)
        a = fm.answer(L.parse("(query :subj cat :rel has :obj ?)"))
        back = L.decode(L.encode(a, Rz.lex, persist=False), Rz.lex)
        self.assertEqual(back["rule"], "inherit_has")
        self.assertEqual(back["because"][1]["obj"], "fur")
        a = fm.answer(L.parse("(query :subj ? :rel is_a :obj animal)"))
        self.assertEqual(sorted(a["subj"]), ["cat", "dog", "mammal"])

    def test_rule_is_a_meaning(self):
        lex = L.Lexicon(path=None)
        m = R.transitive("is_a").meaning()
        back = L.decode(L.encode(m, lex, persist=False), lex)
        self.assertEqual(back["then"]["rel"], "is_a")
        self.assertEqual(back["cond"][0]["subj"], "?x")


class TestKB(unittest.TestCase):
    def test_tell_and_reproduce(self):
        with tempfile.TemporaryDirectory() as d:
            lex = L.Lexicon(path=None)
            kb = K.KB(path=Path(d) / "kb.jsonl", lex=lex)
            a = kb.tell("memory", "x", "part_of", "y")
            b = kb.tell("memory", "y", "part_of", "z")
            kb.grade("lexicon", a, True, "observed")
            kb.grade("lexicon", b, True, "observed")
            Rz = R.Reasoner(lex=lex)
            fm = R.FactMemory(Rz, min_trust=0.6)
            for fid, s, r, o, t in kb.facts():
                fm.add(s, r, o, conf=t)
            new = fm.infer(R.DEFAULT_RULES, min_conf=0.3)
            self.assertEqual([(f.s, f.r, f.o) for f in new], [("x", "part_of", "z")])
            fm.tell_kb(kb, new)
            fid = R.fact_id("x", "part_of", "z")
            self.assertTrue(kb.facts_[fid]["check"].startswith("reason:transitive_part_of:"))
            self.assertIs(kb.reproduce("courier", fid), True)   # someone else re-derives it
            # a forged derivation fails the recheck
            kb.tell("reasoner", "x", "part_of", "q", check=f"reason:transitive_part_of:{a},{b}")
            self.assertIs(kb.reproduce("courier", R.fact_id("x", "part_of", "q")), False)

    def test_source_checkers(self):
        self.assertTrue(R.check_imports(None, "imports:shared/reason.py:language"))
        self.assertFalse(R.check_imports(None, "imports:shared/reason.py:protocol"))
        self.assertTrue(R.check_grep(None, "grep:shared/reason.py:owner: reasoner"))
        self.assertIsNone(R.check_grep(None, "grep:../../etc/passwd:root"))


if __name__ == "__main__":
    unittest.main()
