"""Tests for reasoner/agent.py on a throwaway KB (never the shared one)."""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "shared"))

from knowledge import KB  # noqa: E402
from reason import ordinal_infer  # noqa: E402
from agent import Reasoner  # noqa: E402


class TestOrdinal(unittest.TestCase):
    def test_sandwich_extrapolate_abstain(self):
        pts = {3: "all", 9: "all", 33: "most", 129: "few", 257: "few"}
        got = {c.param: (c.value, c.rule) for c in
               ordinal_infer(pts, [3, 5, 9, 17, 33, 65, 129, 257, 513])}
        self.assertEqual(got[5], ("all", "sandwich"))
        self.assertEqual(got[513], ("few", "extrapolate"))
        self.assertNotIn(17, got)   # all | most boundary: I don't know
        self.assertNotIn(65, got)

    def test_non_monotone_says_nothing(self):
        self.assertEqual(ordinal_infer({1: "a", 2: "b", 3: "a"}, [1, 1.5, 2, 3, 4]), [])


class TestAgent(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="reasoner-test-")
        self.kb = KB(root=self.dir)

    def tearDown(self):
        self.kb.close()

    def _fact(self, author, s, r, o, ctx=None, graders=("courier",)):
        cid = self.kb.tell(author, s, r, o, context=ctx)
        for g in graders:
            self.kb.grade(g, cid, True, "test")
        return cid

    def test_closure_tells_with_evidence(self):
        a = self._fact("lexicon", "cat", "is_a", "mammal")
        b = self._fact("lexicon", "mammal", "is_a", "animal")
        r = Reasoner(self.kb)
        made = r.infer_closure()
        self.assertEqual(len(made), 1)
        cid, glyph = made[0]
        c = self.kb.claim(cid)
        self.assertEqual((c.subject, c.relation, c.value), ("cat", "is_a", "animal"))
        self.assertEqual(c.evidence, [a, b])
        self.assertEqual(c.author, "reasoner")
        # idempotent: a second turn tells nothing new
        self.assertEqual(Reasoner(self.kb).infer_closure(), [])

    def test_ungraded_premises_carry_nothing(self):
        self._fact("lexicon", "cat", "is_a", "mammal", graders=())
        self._fact("lexicon", "mammal", "is_a", "animal", graders=())
        for k, v in (("3", "all"), ("9", "all"), ("33", "all")):
            self._fact("memory", "bundle", "recall", v, {"k": k}, graders=())
        self.assertEqual(Reasoner(self.kb).infer_ordinal(), [])

    def test_ordinal_on_world_family(self):
        for k, v in (("3", "all"), ("9", "all"), ("33", "all"), ("129", "few"),
                     ("513", "few")):
            self._fact("memory", "bundle", "recall", v, {"k": k})
        made = Reasoner(self.kb).infer_ordinal()
        got = {self.kb.claim(c).context["k"]: self.kb.claim(c).value for c, _ in made}
        self.assertEqual(got.get("5"), "all")
        self.assertEqual(got.get("17"), "all")
        self.assertEqual(got.get("257"), "few")
        self.assertNotIn("65", got)       # the boundary: no conclusion

    def test_vetoes_lower_rule_confidence(self):
        for k, v in (("3", "all"), ("9", "all"), ("33", "all")):
            self._fact("memory", "bundle", "recall", v, {"k": k})
        r = Reasoner(self.kb)
        made = r.infer_ordinal()
        before = r.rule_reliability()
        for cid, _ in made:
            self.kb.grade("lexicon", cid, False, "test veto")
        after = Reasoner(self.kb).rule_reliability()
        self.assertEqual(sum(after[k]["graded"] for k in ("sandwich", "extrapolate")),
                         len(made))
        for k in ("sandwich", "extrapolate"):
            self.assertLess(after[k]["conf"], before[k]["conf"])

    def test_vetoed_premise_makes_inference_stale(self):
        a = self._fact("lexicon", "cat", "is_a", "mammal")
        self._fact("lexicon", "mammal", "is_a", "animal")
        r = Reasoner(self.kb)
        r.infer_closure()
        self.assertEqual(r.stale(), [])
        for g in ("memory", "courier", "reasoner"):
            self.kb.grade(g, a, False, "test refutation")
        st = Reasoner(self.kb).stale()
        self.assertEqual(len(st), 1)
        self.assertEqual(st[0]["premise"], a)

    def test_infer_one_answers_what_the_kb_cannot(self):
        for k, v in (("3", "all"), ("9", "all"), ("33", "all"), ("129", "few")):
            self._fact("memory", "bundle", "recall", v, {"k": k})
        r = Reasoner(self.kb)
        self.assertEqual(r.infer_one("bundle", "recall", {"k": "20"})["value"], "all")
        self.assertIsNone(r.infer_one("bundle", "recall", {"k": "65"}))  # boundary
        self._fact("lexicon", "a", "part_of", "b")
        self._fact("lexicon", "b", "part_of", "c")
        self.assertEqual(r.infer_one("a", "part_of", {})["value"], "c")

    def test_grades_others_by_reproducing(self):
        good = self.kb.tell("memory", "bundle", "recall", "all", context={"k": "3"})
        bad = self.kb.tell("memory", "bundle", "recall", "all", context={"k": "513"})
        a = self._fact("lexicon", "x", "part_of", "y")
        b = self._fact("lexicon", "y", "part_of", "z")
        derived = self.kb.tell("courier", "x", "part_of", "z", evidence=[a, b])
        wrong = self.kb.tell("courier", "x", "part_of", "q", evidence=[a, b])
        r = Reasoner(self.kb)
        t = r.grade_pending()
        g = {cid: [x["ok"] for x in self.kb.grades(cid) if x["grader"] == "reasoner"]
             for cid in (good, bad, derived, wrong)}
        self.assertEqual(g[good], [True])
        self.assertEqual(g[bad], [False])
        self.assertEqual(g[derived], [True])
        self.assertEqual(g[wrong], [False])


if __name__ == "__main__":
    unittest.main()
