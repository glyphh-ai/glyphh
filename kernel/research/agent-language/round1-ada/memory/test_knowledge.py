"""Tests for shared/knowledge.py (run: python3 -m unittest -v test_knowledge
from agents/memory). Every KB here lives in a temp dir, never shared/kb."""

import multiprocessing as mp
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "shared"))
sys.path.insert(0, str(HERE.parents[1] / "kernel_v1"))

import numpy as np  # noqa: E402
from glyphh_kernel import Space, bind, sim  # noqa: E402
from knowledge import KB, SelfGrade, frame_glyph, _role, _word  # noqa: E402

GRADERS = ("lexicon", "courier", "memory")


def _writer(root, author, n):          # for the multi-process test
    kb = KB(root)
    for i in range(n):
        kb.tell(author, f"s{author}{i}", "rel", "v")
    kb.close()


class TestKB(unittest.TestCase):
    def setUp(self):
        self.kb = KB(tempfile.mkdtemp(prefix="kbtest-"))

    def tearDown(self):
        self.kb.close()

    def known(self, s="cat", r="is_a", v="mammal", author="reasoner"):
        cid = self.kb.tell(author, s, r, v)
        for g in GRADERS:
            if g != author:
                self.kb.grade(g, cid, True, "reproduced")
        return cid

    # ── grading rules ───────────────────────────────────────────────
    def test_unknown_then_claimed_then_known(self):
        self.assertEqual(self.kb.ask("cat", "is_a").status, "unknown")
        cid = self.kb.tell("reasoner", "cat", "is_a", "mammal")
        b = self.kb.ask("cat", "is_a")
        self.assertEqual((b.status, b.value, b.pending), ("claimed", "mammal", [cid]))
        self.kb.grade("lexicon", cid, True)
        self.assertEqual(self.kb.ask("cat", "is_a").status, "uncertain")
        self.kb.grade("courier", cid, True)
        self.assertEqual(self.kb.ask("cat", "is_a").status, "uncertain")
        self.kb.grade("memory", cid, True)
        b = self.kb.ask("cat", "is_a")
        self.assertEqual((b.status, b.value, b.count), ("known", "mammal", 3))
        self.assertEqual({r["author"] for r in b.receipts}, set(GRADERS))

    def test_never_self_graded(self):
        cid = self.kb.tell("reasoner", "cat", "is_a", "mammal")
        with self.assertRaises(SelfGrade):
            self.kb.grade("reasoner", cid, True)
        self.assertEqual(len(self.kb.wins), 0)

    def test_same_grader_twice_counts_once(self):
        cid = self.kb.tell("reasoner", "cat", "is_a", "mammal")
        for _ in range(3):
            self.kb.grade("lexicon", cid, True)
        b = self.kb.ask("cat", "is_a")
        self.assertEqual((b.status, b.count), ("uncertain", 1))

    def test_other_questions_do_not_vote(self):
        self.known("cat", "is_a", "mammal")
        # same relation, different subject: sim ~0.5 (tie-break) < 0.70
        self.assertEqual(self.kb.ask("dog", "is_a").status, "unknown")
        self.assertEqual(self.kb.ask("cat", "eats").status, "unknown")

    def test_one_refutation_vetoes_exact_fact(self):
        cid = self.known()
        self.kb.grade("courier", cid, False, "got reptile")  # changes mind
        b = self.kb.ask("cat", "is_a")
        self.assertEqual(b.status, "vetoed")

    def test_veto_lets_the_alternative_through(self):
        old = self.known(v="mammal", author="orchestrator")
        new = self.kb.tell("lexicon", "cat", "is_a", "robot")
        for g in ("courier", "memory", "reasoner"):
            self.kb.grade(g, new, True)
        self.kb.grade("reasoner", old, True)  # 4 wins mammal, 3 robot
        self.assertEqual(self.kb.ask("cat", "is_a").value, "mammal")
        self.kb.grade("memory", old, False)   # mammal suppressed
        b = self.kb.ask("cat", "is_a")
        self.assertEqual((b.status, b.value), ("known", "robot"))

    def test_refuted_claim_without_wins_is_vetoed(self):
        cid = self.kb.tell("memory", "k65", "recall", "all")
        self.kb.grade("courier", cid, False, "got most")
        b = self.kb.ask("k65", "recall")
        self.assertEqual((b.status, b.value), ("vetoed", "all"))
        other = self.kb.tell("lexicon", "k65", "recall", "most")
        b = self.kb.ask("k65", "recall")
        self.assertEqual((b.status, b.value), ("claimed", "most"))

    def test_contested_when_graders_split(self):
        a = self.kb.tell("lexicon", "x", "r", "p")
        b = self.kb.tell("courier", "x", "r", "q")
        self.kb.grade("memory", a, True)
        self.kb.grade("reasoner", a, True)
        self.kb.grade("memory", b, True)
        self.kb.grade("reasoner", b, True)
        self.assertEqual(self.kb.ask("x", "r").status, "contested")

    def test_verify_reproduces(self):
        cid = self.kb.tell("reasoner", "two", "plus_two", "4")
        self.assertTrue(self.kb.verify("lexicon", cid, lambda c: str(2 + 2)))
        self.assertFalse(self.kb.verify("courier", cid, lambda c: "5"))
        self.assertIsNone(self.kb.verify("memory", cid, lambda c: None))
        self.assertEqual([g["ok"] for g in self.kb.grades(cid)], [True, False])

    def test_feedback_grades_claims_behind_answer(self):
        cid = self.known()
        b = self.kb.ask("cat", "is_a")
        # reasoner authored it: its feedback grades nothing
        self.assertEqual(self.kb.feedback("reasoner", b, False), 0)
        self.assertEqual(self.kb.feedback("courier", b, False), 1)
        self.assertEqual(self.kb.ask("cat", "is_a").status, "vetoed")

    def test_pending_is_others_ungraded(self):
        a = self.kb.tell("reasoner", "a", "r", "1")
        self.kb.tell("memory", "b", "r", "1")
        self.assertEqual([c.id for c in self.kb.pending("memory")], [a])
        self.kb.grade("memory", a, True)
        self.assertEqual(self.kb.pending("memory"), [])

    # ── the language ────────────────────────────────────────────────
    def test_question_is_a_space_situation(self):
        sit = {"subject": "cat", "relation": "is_a", "k": "3"}
        g = frame_glyph(sit)
        self.assertTrue(np.array_equal(g, Space().encode(sit)))

    def test_fact_glyph_decodes_object(self):
        cid = self.known()
        g = self.kb.claim(cid).glyph()
        self.assertGreater(sim(bind(g, _role("object")), _word("mammal")), 0.3)
        self.assertLess(abs(sim(bind(g, _role("object")), _word("reptile"))), 0.08)

    def test_concept_bundles_known_facts(self):
        self.known("cat", "is_a", "mammal")
        self.known("cat", "eats", "fish")
        self.kb.tell("reasoner", "cat", "says", "woof")   # claimed only
        g = self.kb.concept("cat")
        o = bind(g, _role("object"))
        self.assertGreater(sim(o, _word("mammal")), 0.15)
        self.assertGreater(sim(o, _word("fish")), 0.15)
        self.assertLess(abs(sim(o, _word("woof"))), 0.08)

    def test_ask_glyph_from_language_question(self):
        from language import Lexicon
        self.known()
        lx = Lexicon(author="test", path=None)
        q = lx.encode(lx.ask("object", subject="cat", relation="is_a"))
        b = self.kb.ask_glyph(q, asker="courier")
        self.assertEqual((b.status, b.value), ("known", "mammal"))

    # ── shared files ────────────────────────────────────────────────
    def test_refresh_sees_other_process_rows(self):
        root = self.kb.root
        ps = [mp.Process(target=_writer, args=(str(root), a, 20))
              for a in ("lexicon", "courier")]
        for p in ps:
            p.start()
        for p in ps:
            p.join()
        self.assertEqual(self.kb.refresh(), 40)
        self.assertEqual(len(self.kb.claims), 40)
        self.assertEqual(self.kb.ask("slexicon3", "rel").status, "claimed")

    def test_audit_and_lineage(self):
        p1 = self.known("a", "r", "1")
        p2 = self.known("b", "r", "1")
        d = self.kb.tell("reasoner", "c", "r", "1", evidence=[p1, p2])
        d2 = self.kb.tell("reasoner", "d", "r", "1", evidence=[d])
        self.assertEqual(self.kb.lineage(d2), [d, p1, p2])
        self.assertEqual(self.kb.suspects(), [])
        self.kb.grade("courier", p1, False)
        self.assertEqual(set(self.kb.suspects()), {d, d2})
        a = self.kb.audit()
        self.assertEqual(a["bad_receipts"], [])
        self.assertEqual(a["superseded"], [f"{p1}~courier"])


class TestVetoRules(unittest.TestCase):
    def _hostile_kb(self, rule):
        kb = KB(tempfile.mkdtemp(prefix="kbveto-"), veto_rule=rule)
        # 10 facts, each told by reasoner and reproduced by 3 honest
        # graders; courier refutes everything
        for i in range(10):
            cid = kb.tell("reasoner", f"f{i}", "r", "v")
            for g in ("lexicon", "memory", "orchestrator"):
                kb.grade(g, cid, True)
            kb.grade("courier", cid, False, "hostile")
        return kb

    def test_nearest_is_erased_by_one_hostile_grader(self):
        kb = self._hostile_kb("nearest")
        self.assertEqual({kb.ask(f"f{i}", "r").status for i in range(10)},
                         {"vetoed"})

    def test_trusted_ignores_unreliable_grader(self):
        kb = self._hostile_kb("trusted")
        self.assertLess(kb.reliability()["courier"], 0.5)
        self.assertEqual({kb.ask(f"f{i}", "r").status for i in range(10)},
                         {"known"})

    def test_trusted_still_vetoes_on_honest_refutation(self):
        kb = self._hostile_kb("trusted")
        cid = kb.all_claims()[0].id
        kb.grade("lexicon", cid, False, "the world changed")
        self.assertEqual(kb.ask("f0", "r").status, "vetoed")


if __name__ == "__main__":
    unittest.main()
