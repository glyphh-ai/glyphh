"""courier/test_protocol.py -- python3 -m unittest courier/test_protocol.py
Private Lexicon(path=None) everywhere; the channel is never written."""
import sys
import unittest
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "courier"))
import language as L  # noqa: E402
import protocol as P  # noqa: E402
import bench  # noqa: E402

warnings.simplefilter("ignore")


def lex():
    x = L.Lexicon(path=None)
    x.learn([f"w{i}" for i in range(50)] + ["cat", "animal", "is_a", "mammal", "dog"], persist=False)
    return x


class Envelope(unittest.TestCase):
    def setUp(self):
        self.lx = lex()

    def test_roundtrip_all_fields(self):
        q = P.compose("reasoner", "memory", "ask", "(query :subj cat :rel is_a :obj ?)", lex=self.lx)
        a = P.compose("memory", "reasoner", "answer", "(fact :subj cat :rel is_a :obj animal)",
                      re=q.id, thread=q.id, conf="conf_hi", lex=self.lx)
        d = P.decode(P.wire(a), known_ids=["mffff00000000", q.id], lex=self.lx)
        self.assertEqual(d.status, "ok")
        self.assertEqual((d.act, d.sender, d.to, d.conf, d.re, d.thread),
                         ("answer", "memory", "reasoner", "conf_hi", q.id, q.id))
        self.assertEqual(L.canonical(d.content), {"act": "fact", "subj": "cat", "rel": "is_a", "obj": "animal"})
        self.assertAlmostEqual(d.agree, 1.0)
        self.assertEqual(d.id, a.id)

    def test_id_is_content_address(self):
        a = P.compose("memory", "all", "tell", "(fact :subj cat :rel is_a :obj animal)", lex=self.lx)
        b = P.compose("memory", "all", "tell", "(fact :subj cat :rel is_a :obj animal)", lex=self.lx)
        c = P.compose("memory", "all", "tell", "(fact :subj dog :rel is_a :obj animal)", lex=self.lx)
        self.assertEqual(a.id, b.id)
        self.assertNotEqual(a.id, c.id)
        self.assertEqual(P.msg_id(P.wire(a)), a.id)

    def test_unknown_parent_not_invented(self):
        a = P.compose("memory", "all", "answer", "(fact :obj animal)", re="m123456789abc", lex=self.lx)
        d = P.decode(P.wire(a), known_ids=["m000000000001", "m000000000002"], lex=self.lx)
        self.assertIsNone(d.re)
        # parent missing from the known ids -> the re-encoding no longer agrees exactly
        self.assertLess(d.agree, 1.0)

    def test_text_compare_is_order_free(self):
        a = P.compose("courier", "all", "tell", "(fact :subj cat :rel is_a :obj animal)", lex=self.lx)
        shuffled = "(tell :to all :check proto_v1 :from courier :content (fact :obj animal :rel is_a :subj cat))"
        self.assertTrue(P._same_text(a, shuffled))
        self.assertFalse(P._same_text(a, shuffled.replace("animal", "dog")))

    def test_text_surface(self):
        a = P.compose("courier", "all", "tell", "(fact :subj cat :rel is_a :obj animal)", re="mabc", lex=self.lx)
        self.assertIn(":re ^mabc", a.text())
        self.assertIn(":check proto_v1", a.text())


class Noise(unittest.TestCase):
    def test_flip_estimate_and_status(self):
        lx = lex()
        rng = np.random.default_rng(7)
        m = P.compose("memory", "reasoner", "tell", "(fact :subj cat :rel is_a :obj mammal)", lex=lx)
        for p, want in [(0.0, "ok"), (0.02, "ok"), (0.15, "noisy"), (0.25, "noisy")]:
            d = P.decode(P.noisy(P.wire(m), p, rng), lex=lx)
            self.assertEqual(d.status, want, p)
            self.assertLess(abs(d.flip_est - p), 0.02, p)
            self.assertEqual(L.canonical(d.content), L.canonical(m.content), p)

    def test_curve_exact_to_025(self):
        for p, exact, err, st in bench.noise_curve(ps=(0.0, 0.1, 0.2, 0.25), n=30):
            self.assertEqual(exact, 1.0, p)
            self.assertLess(err, 0.01, p)

    def test_garbage_classes(self):
        out = bench.foreign(n=40)
        self.assertEqual(out["random"], {"foreign": 40})
        self.assertEqual(out["other_language"], {"foreign": 40})
        self.assertEqual(out["zeros"], {"malformed": 40})
        self.assertEqual(out["bare_meaning"], {"bare": 40})
        self.assertNotIn("ok", out["text_bytes"])

    def test_malformed_shapes(self):
        self.assertEqual(P.decode(None).status, "malformed")
        self.assertEqual(P.decode(np.zeros(10, np.uint8)).status, "malformed")
        self.assertEqual(P.decode(np.zeros(1024, np.float32)).status, "malformed")


class Conversation(unittest.TestCase):
    def setUp(self):
        self.lx = lx = lex()
        self.q = P.compose("reasoner", "memory", "ask", "(query :subj cat :rel is_a :obj ?)", lex=lx)
        self.a = P.compose("memory", "reasoner", "answer", "(fact :obj mammal)", re=self.q.id,
                           thread=self.q.id, lex=lx)
        self.p = P.compose("lexicon", "all", "propose", "(fact :subj dog :rel is_a :obj mammal)", lex=lx)
        self.y = P.compose("courier", "lexicon", "agree", "(fact :subj dog :rel is_a :obj mammal)",
                           re=self.p.id, thread=self.p.id, lex=lx)
        self.n = P.compose("memory", "lexicon", "disagree", "(fact :subj dog :rel is_a :obj mammal)",
                           re=self.p.id, thread=self.p.id, lex=lx)
        self.self_agree = P.compose("lexicon", "all", "agree", "(fact :subj dog :rel is_a :obj mammal)",
                                    re=self.p.id, thread=self.p.id, lex=lx)
        self.u = P.compose("reasoner", "memory", "ask", "(query :subj dog :rel eats :obj ?)", lex=lx)
        self.ua = P.compose("memory", "reasoner", "answer", "(fact :subj dog :rel eats :obj unknown)",
                            re=self.u.id, lex=lx)
        # decode everything from payloads, as a receiver would
        known, self.msgs = [], []
        for m in (self.q, self.a, self.p, self.y, self.n, self.self_agree, self.u, self.ua):
            self.msgs.append(P.decode(P.wire(m), known_ids=known, lex=lx))
            known.append(m.id)

    def test_distill(self):
        facts = P.distill_all(self.msgs)
        got = {L.show(f["fact"]): f for f in facts}
        self.assertIn("(:subj cat :rel is_a :obj mammal)", got)
        qa = got["(:subj cat :rel is_a :obj mammal)"]
        self.assertEqual((qa["src"], qa["asked_by"]), ("memory", "reasoner"))
        pr = got["(:subj dog :rel is_a :obj mammal)"]
        self.assertEqual(pr["endorsed"], ["courier"])      # self-agree by lexicon ignored
        self.assertEqual(pr["disputed"], ["memory"])
        self.assertNotIn("(:subj dog :rel eats :obj unknown)", got)   # abstention establishes nothing

    def test_threads_group_by_root(self):
        ths = P.Thread.all(self.msgs)
        self.assertEqual(len(ths[self.q.id].messages), 2)
        self.assertEqual(len(ths[self.p.id].messages), 4)

    def test_thread_vector_turns(self):
        for T, acc in bench.thread_turns(lengths=(8, 32), n=3):
            self.assertEqual(acc, 1.0, T)

    def test_pending(self):
        pend = P.pending("memory", self.msgs)
        self.assertEqual([m.id for m in pend], [])          # both questions answered by memory
        pend_l = P.pending("lexicon", self.msgs)
        self.assertEqual(pend_l, [])                        # questions were addressed to memory
        extra = P.decode(P.wire(P.compose("courier", "all", "ask", "(query :subj w1 :rel is_a :obj ?)",
                                          lex=self.lx)), lex=self.lx)
        self.assertEqual([m.id for m in P.pending("lexicon", self.msgs + [extra])], [extra.id])

    def test_to_kb_with_fake_kb(self):
        class FakeKB:
            def __init__(s): s.t, s.g = [], []
            def tell(s, a, *spo): s.t.append((a,) + spo); return "f%d" % len(s.t)
            def grade(s, a, fid, ok, how="x"): s.g.append((a, fid, ok))
        kb = FakeKB()
        n = P.to_kb(P.distill_all(self.msgs), kb)
        self.assertEqual(n["told"], 2)
        self.assertIn(("memory", "cat", "is_a", "mammal"), kb.t)
        self.assertEqual(sorted(kb.g), [("courier", "f2", True), ("memory", "f2", False)])

    def test_lift_bare_proposal(self):
        bare = L.to_wire(L.encode(L.parse("(propose :subj w1 :rel is_a :obj w2 :agent lexicon)"),
                                  self.lx, persist=False))
        d = P.decode(bare, lex=self.lx)
        self.assertEqual(d.status, "bare")
        agree = P.decode(P.wire(P.compose("memory", "lexicon", "agree", "(fact :subj w1)", re=d.id,
                                          lex=self.lx)), known_ids=[d.id], lex=self.lx)
        f = P.distill_all([d, agree])
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["src"], f[0]["endorsed"]), ("lexicon", ["memory"]))


class LongContent(unittest.TestCase):
    def test_parts_reassemble_any_order_and_detect_missing(self):
        lx = lex(); rng = np.random.default_rng(3)
        W = [f"w{i}" for i in range(50)]
        items = [{"subj": str(a), "rel": "is_a", "obj": str(b)}
                 for a, b in (rng.choice(W, 2, replace=False) for _ in range(40))]
        parts = P.compose_parts("memory", "all", "tell", items, lex=lx)
        self.assertGreater(len(parts), 1)
        ids = [p.id for p in parts]
        dec = [P.decode(P.wire(parts[i]), known_ids=ids, lex=lx) for i in rng.permutation(len(parts))]
        self.assertEqual(L.canonical(P.reassemble(dec, parts[0].id, lex=lx)), L.canonical(items))
        self.assertIsNone(P.reassemble([d for d in dec if d.id != parts[-1].id], parts[0].id, lex=lx))


class Routing(unittest.TestCase):
    def test_better_than_chance(self):
        self.assertGreater(bench.routing(n_q=100), 0.5)          # chance = 0.25


class Checks(unittest.TestCase):
    def test_proto_checks(self):
        self.assertTrue(P.check(None, "proto:roundtrip:(fact :subj a :rel b :obj [c d])"))
        self.assertTrue(P.check(None, "proto:noise:0.2:20:0.95"))
        self.assertFalse(P.check(None, "proto:noise:0.45:20:0.5"))
        self.assertTrue(P.check(None, "proto:foreign:50"))
        self.assertIsNone(P.check(None, "proto:nonsense"))


if __name__ == "__main__":
    unittest.main()
