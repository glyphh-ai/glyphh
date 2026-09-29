"""unittest for shared/language.py.  Run: python3 -m unittest lexicon/test_language.py -v"""
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))
import language as L  # noqa: E402

SAMPLES = [
    "(assert :subj cat :rel is_a :obj animal)",
    "(ask :from reasoner :to memory :content (fact :subj cat :rel is_a :obj ?))",
    "(answer :re (ask :subj cat :rel is_a :obj ?) :content (fact :subj cat :rel is_a :obj animal) "
    ":conf conf_hi :because [(fact :subj cat :rel is_a :obj mammal) (fact :subj mammal :rel is_a :obj animal)] "
    ":rule transitive)",
    "(grade :agent memory :subj (fact :subj sky :rel color :obj blue) :obj yes)",
    "(define :name grandparent :def (rule :cond [(fact :subj ?x :rel parent :obj ?y) (fact :subj ?y :rel parent :obj ?z)] "
    ":then (fact :subj ?x :rel grandparent :obj ?z)))",
    "[one two three four five six]",
    '(assert :subj "a phrase with spaces" :rel says :obj "quote \\" inside")',
    "word",
]


def lex():
    return L.Lexicon(path=None)


class TestAlgebra(unittest.TestCase):
    def test_atoms_deterministic_across_processes(self):
        code = ("import sys; sys.path.insert(0, %r); import language as L, hashlib; "
                "print(hashlib.sha256(L.atom('cat').tobytes()).hexdigest())") % str(ROOT / "shared")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
        import hashlib
        self.assertEqual(out, hashlib.sha256(L.atom("cat").tobytes()).hexdigest())

    def test_atoms_quasi_orthogonal(self):
        A = np.stack([L.atom(f"x{i}") for i in range(200)]).astype(np.float32)
        S = A @ A.T / L.D
        off = S[~np.eye(200, dtype=bool)]
        self.assertLess(np.abs(off).max(), 6 / np.sqrt(L.D))
        self.assertAlmostEqual(float(np.abs(off).std() * np.sqrt(L.D)), 0.6, delta=0.2)  # |N(0,1)| std ~0.6

    def test_bind_self_inverse_and_permute(self):
        a, b = L.atom("a"), L.atom("b")
        self.assertTrue(np.array_equal(L.unbind(L.bind(a, b), b), a))
        self.assertLess(abs(L.sim(L.bind(a, b), a)), 0.05)
        self.assertLess(abs(L.sim(L.permute(a), a)), 0.05)
        self.assertTrue(np.array_equal(L.permute(L.permute(a, 1), -1), a))

    def test_roles_case_insensitive(self):
        self.assertTrue(np.array_equal(L.role("SUBJ"), L.role("subj")))
        lx = lex()
        d = L.decode(L.encode({"ACT": "assert", "SUBJ": "cat"}, lx, persist=False), lx)
        self.assertEqual(d["SUBJ"], "cat"); self.assertEqual(d.get("subj"), "cat")
        self.assertEqual(d, {"act": "assert", "subj": "cat"})
        self.assertEqual(d, {"ACT": "assert", "SUBJ": "cat"})

    def test_wire_roundtrip(self):
        v = L.encode(L.parse(SAMPLES[2]), lex(), persist=False)
        w = L.to_wire(v)
        self.assertEqual((w.dtype, w.shape), (np.uint8, (L.D // 8,)))
        self.assertTrue(np.array_equal(L.from_wire(w), v))


class TestGrammar(unittest.TestCase):
    def test_parse_show_inverse(self):
        for s in SAMPLES:
            m = L.parse(s)
            self.assertEqual(L.parse(L.show(m)), m, s)

    def test_roundtrip_samples_via_wire(self):
        lx = lex()
        for s in SAMPLES:
            m = L.parse(s)
            r = L.read_back(L.to_wire(L.encode(m, lx, persist=False)), lx)
            self.assertEqual(r.meaning, L.canonical(m), s)
            self.assertGreater(r.confidence, lx.threshold())

    def test_nesting_is_order_sensitive(self):
        lx = lex()
        a = L.encode({"subj": {"obj": "x"}}, lx, persist=False)
        b = L.encode({"obj": {"subj": "x"}}, lx, persist=False)
        self.assertLess(abs(L.sim(a, b)), 0.35)   # only the top FRAME marker is shared (1 of 4 leaves)
        self.assertEqual(L.decode(a, lx), {"subj": {"obj": "x"}})
        self.assertEqual(L.decode(b, lx), {"obj": {"subj": "x"}})

    def test_list_order_matters(self):
        lx = lex()
        self.assertEqual(L.decode(L.encode(["a", "b", "c"], lx, persist=False), lx), ["a", "b", "c"])
        self.assertEqual(L.decode(L.encode(["c", "b", "a"], lx, persist=False), lx), ["c", "b", "a"])

    def test_random_nested_meanings(self):
        rng = np.random.default_rng(42)
        lx = lex()
        words = [f"w{i}" for i in range(500)]
        roles = list(L.ROLES)

        def gen(depth):
            k = int(rng.integers(1, 5))
            m = {}
            for r in rng.choice(roles, k, replace=False):
                x = rng.random()
                if depth > 0 and x < 0.3:
                    m[str(r)] = gen(depth - 1)
                elif depth > 0 and x < 0.4:
                    m[str(r)] = [str(w) for w in rng.choice(words, int(rng.integers(1, 4)))]
                else:
                    m[str(r)] = str(rng.choice(words))
            return m
        ok = 0
        for _ in range(100):
            m = gen(3)
            if L.leaf_count(m) > L.max_leaves():
                continue
            ok += L.decode(L.encode(m, lx, persist=False), lx) == m
        self.assertGreaterEqual(ok, 99)

    def test_embedded_vector_is_quotable(self):
        lx = lex()
        q = L.encode(L.parse("(ask :subj cat :rel is_a :obj ?)"), lx, persist=False)
        msg = L.encode({"act": "answer", "re": q, "obj": "animal"}, lx, persist=False)
        u = L.unbind_role(msg, "re")
        self.assertGreater(L.sim(u, q), 0.3)          # the reply points at the question
        d = L.decode(msg, lx)                          # and even the quoted frame reads back
        self.assertEqual(d["obj"], "animal")
        self.assertEqual(d["re"]["subj"], "cat")

    def test_question_slot_unbinding(self):
        lx = lex()
        v = L.encode(L.parse("(ask :content (fact :subj cat :rel is_a :obj ?))"), lx, persist=False)
        self.assertEqual(lx.cleanup(L.unbind_role(v, "content", "obj"))[0], "?")


class TestReading(unittest.TestCase):
    def test_noise_is_noise(self):
        rng = np.random.default_rng(1)
        lx = lex()
        kinds = [L.read_back(rng.integers(0, 256, L.D // 8, dtype=np.uint8), lx).kind for _ in range(50)]
        self.assertEqual(kinds.count("noise"), 50)

    def test_bitflip_tolerance(self):
        lx = lex()
        m = L.parse(SAMPLES[2])
        bits = np.unpackbits(L.to_wire(L.encode(m, lx, persist=False)))
        rng = np.random.default_rng(3)
        bits[rng.random(bits.size) < 0.1] ^= 1
        self.assertEqual(L.decode(np.packbits(bits), lx), m)

    def test_unknown_word_needs_vocab(self):
        lx = lex()
        other = L.Lexicon(path=None)
        v = L.encode({"subj": "zyzzyva"}, lx, persist=False)
        self.assertNotEqual(L.decode(v, other), {"subj": "zyzzyva"})   # reader lacks the word
        other.learn(["zyzzyva"], persist=False)
        self.assertEqual(L.decode(v, other), {"subj": "zyzzyva"})

    def test_vocab_file_shares_words(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "vocab.txt"
            a = L.Lexicon(path=p); b = L.Lexicon(path=p)
            v = L.encode({"subj": "quokka", "newrole": "wombat"}, a)
            b.reload()
            self.assertEqual(L.decode(v, b), {"subj": "quokka", "newrole": "wombat"})
            self.assertIn(":newrole", p.read_text())

    def test_budget_warning(self):
        lx = lex()
        big = [str(i) for i in range(32)]
        m = {"#0": big, "subj": big, "obj": big, "val": big}   # 136 leaves > 102
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            L.encode(m, lx, persist=False)
            self.assertTrue(any("budget" in str(x.message) for x in w))

    def test_say_hear(self):
        text, payload = L.say("(ask :subj cat :rel is_a :obj ?)", lex())
        self.assertEqual(text, "(ask :subj cat :rel is_a :obj ?)")
        lx = lex(); lx.learn(["cat", "is_a"], persist=False)
        self.assertEqual(L.show(L.read_back(payload, lx).meaning), text)


if __name__ == "__main__":
    unittest.main()
