"""unittest for shared/dictionary.py.  Run: python3 -m unittest lexicon/test_dictionary.py -v"""
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))
import language as L  # noqa: E402
import dictionary as Dn  # noqa: E402


def fresh():
    lex = L.Lexicon(path=None)
    return lex, Dn.Dictionary(path=None, lex=lex)


def chain(n):
    """A proof with n premises: fact_i = (fact :subj e_i :rel is_a :obj e_{i+1})."""
    return [{"act": "fact", "subj": f"e{i}", "rel": "is_a", "obj": f"e{i+1}"} for i in range(n)]


class TestDictionary(unittest.TestCase):
    def test_define_expand_compress_roundtrip(self):
        lex, dic = fresh()
        f = L.parse("(fact :subj mammal :rel is_a :obj animal)")
        dic.define("lexicon", "mammal_is_animal", f, persist=False)
        m = L.parse("(ask :content (fact :subj mammal :rel is_a :obj animal) :because [(fact :subj mammal :rel is_a :obj animal) x])")
        s = dic.compress(m)
        self.assertEqual(s, {"act": "ask", "content": "mammal_is_animal", "because": ["mammal_is_animal", "x"]})
        self.assertEqual(dic.expand(s), m)
        self.assertLess(L.leaf_count(s), L.leaf_count(m))

    def test_compress_is_order_free_for_frames(self):
        lex, dic = fresh()
        dic.define("lexicon", "w", {"subj": "a", "obj": "b"}, persist=False)
        self.assertEqual(dic.compress({"obj": "b", "subj": "a"}), "w")

    def test_definitions_can_use_defined_words(self):
        lex, dic = fresh()
        dic.define("lexicon", "f1", L.parse("(fact :subj a :rel r :obj b)"), persist=False)
        dic.define("lexicon", "pair", L.parse("[f1 f1]"), persist=False)
        big = L.parse("(tell :content [(fact :subj a :rel r :obj b) (fact :subj a :rel r :obj b)])")
        self.assertEqual(dic.compress(big), {"act": "tell", "content": "pair"})
        self.assertEqual(dic.expand(dic.compress(big)), big)

    def test_no_redefinition(self):
        lex, dic = fresh()
        dic.define("lexicon", "w", {"subj": "a"}, persist=False)
        with self.assertRaises(ValueError):
            dic.define("courier", "w", {"subj": "b"}, persist=False)
        with self.assertRaises(ValueError):
            dic.define("courier", "w2", {"subj": "a"}, persist=False)

    def test_refuses_names_already_in_use(self):
        lex, dic = fresh()
        L.encode({"subj": "dictionary.py", "rel": "part_of", "obj": "x"}, lex, persist=False)
        with self.assertRaises(ValueError):
            dic.define("lexicon", "dictionary.py", {"subj": "a", "obj": "b"}, persist=False)
        self.assertIsNone(dic.learn_from({"act": "define", "name": "dictionary.py",
                                          "def": {"subj": "a", "obj": "b"}}, persist=False,
                                         in_use=["dictionary.py"]))

    def test_capacity_gain(self):
        """A 30-premise proof (159 leaves) is over budget and does NOT decode exactly;
        with its premises defined as words it is 39 leaves, decodes exactly over the
        wire, and expands back to the original."""
        lex, dic = fresh()
        premises = chain(30)
        m = {"act": "answer", "content": {"act": "fact", "subj": "e0", "rel": "is_a", "obj": "e30"},
             "because": premises, "rule": "transitive"}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.assertGreater(L.leaf_count(m), L.max_leaves())
            self.assertNotEqual(L.decode(L.to_wire(L.encode(m, lex, persist=False)), lex), m)
        for i, p in enumerate(premises):
            dic.define("lexicon", f"p{i}", p, persist=False)
        s = dic.compress(m)
        self.assertLessEqual(L.leaf_count(s), L.max_leaves())
        got = L.decode(L.to_wire(L.encode(s, lex, persist=False)), lex)
        self.assertEqual(got, s)
        self.assertEqual(dic.expand(got), m)

    def test_mine_and_adopt(self):
        lex, dic = fresh()
        f = L.parse("(fact :subj cat :rel is_a :obj mammal)")
        corpus = [{"act": "ask", "content": f}, {"act": "tell", "content": f, "conf": "conf_hi"},
                  {"act": "grade", "subj": f, "obj": "yes"}, L.parse("(tell :content (fact :subj x :rel y :obj z))")]
        cands = dic.mine(corpus, min_count=2, min_leaves=4)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0][1], 3)
        self.assertEqual(cands[0][2], f)
        dic.adopt("lexicon", cands, persist=False)
        before = sum(L.leaf_count(m) for m in corpus)
        after = sum(L.leaf_count(dic.compress(m)) for m in corpus)
        self.assertEqual(before - after, 3 * (L.leaf_count(f) - 1))

    def test_shared_file_and_learn_from(self):
        with tempfile.TemporaryDirectory() as d:
            vp, dp = Path(d) / "vocab.txt", Path(d) / "dict.jsonl"
            la, lb = L.Lexicon(path=vp), L.Lexicon(path=vp)
            a = Dn.Dictionary(path=dp, lex=la)
            b = Dn.Dictionary(path=dp, lex=lb)
            msg = a.define("lexicon", "felid", L.parse("(fact :subj ?x :rel is_a :obj cat)"))
            b.reload(); lb.reload()
            self.assertIn("felid", b)
            # the define message itself travels in the language and teaches a third reader
            lc = L.Lexicon(path=vp)
            c = Dn.Dictionary(path=None, lex=lc)
            heard = L.decode(L.to_wire(L.encode(msg, la)), lc)
            self.assertEqual(c.learn_from(heard, by="lexicon", persist=False), "felid")
            self.assertEqual(c.expand("felid"), L.parse("(fact :subj ?x :rel is_a :obj cat)"))

    def test_sense_makes_concepts_similar(self):
        lex, dic = fresh()
        dic.define("lexicon", "cat_mammal", L.parse("(fact :subj cat :rel is_a :obj mammal)"), persist=False)
        dic.define("lexicon", "dog_mammal", L.parse("(fact :subj dog :rel is_a :obj mammal)"), persist=False)
        dic.define("lexicon", "sky_blue", L.parse("(fact :subj sky :rel color :obj blue)"), persist=False)
        self.assertLess(abs(L.sim(L.atom("cat_mammal"), L.atom("dog_mammal"))), 0.05)  # atoms: unrelated
        s_same = L.sim(dic.sense("cat_mammal"), dic.sense("dog_mammal"))
        s_diff = L.sim(dic.sense("cat_mammal"), dic.sense("sky_blue"))
        self.assertGreater(s_same, 0.5)
        self.assertLess(s_diff, s_same - 0.2)
        q = L.encode(L.parse("(fact :subj lion :rel is_a :obj mammal)"), lex, persist=False)
        self.assertIn(dic.recognise(q, k=2)[0][0], ("cat_mammal", "dog_mammal"))


if __name__ == "__main__":
    unittest.main()
