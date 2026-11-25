"""Tests for shared/protocol.py.  Run: python3 -m unittest courier/test_protocol.py

All tests use a private Lexicon (path=None) and a temp channel log, so
they never touch the shared codebook or the real channel.
"""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

AGENTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENTS_DIR / "shared"))
sys.path.insert(0, str(AGENTS_DIR))
import channel  # noqa: E402
import protocol as P  # noqa: E402
from language import Lexicon  # noqa: E402


def lex(seed=42):
    return Lexicon(path=None, seed=seed, author="test")


class Envelope(unittest.TestCase):
    def setUp(self):
        self.lx = lex()

    def test_roundtrip_fields_and_content(self):
        c = {"subject": "bundle", "relation": "capacity", "object": "about_24"}
        g = P.Message("courier", "memory", "tell", c).glyph(self.lx)
        d = P.decode(g, self.lx)
        self.assertTrue(d.valid)
        self.assertEqual((d.get("from"), d.get("to"), d.get("act")),
                         ("courier", "memory", "tell"))
        self.assertEqual(d.content, c)
        self.assertGreater(d.fidelity, 0.99)

    def test_word_content(self):
        g = P.Message("memory", "all", "done", "done").glyph(self.lx)
        self.assertEqual(P.decode(g, self.lx).content, "done")

    def test_envelope_is_a_sentence_lexicon_can_read(self):
        c = {"subject": "x", "relation": "y", "object": "?"}
        g = P.Message("reasoner", "all", "ask", c).glyph(self.lx)
        m = self.lx.decode(g)
        self.assertEqual(m["act"], "ask")
        self.assertEqual(m["from"], "reasoner")
        self.assertEqual(m["content"], c)

    def test_unknown_act_refused(self):
        with self.assertRaises(ValueError):
            P.Message("a", "b", "shout", "x").glyph(self.lx)

    def test_reply_to_and_thread_resolve(self):
        m1 = P.Message("reasoner", "all", "ask", {"subject": "a", "object": "?"}).glyph(self.lx)
        others = {f"o{i}": P.Message("memory", "all", "tell", {"subject": f"s{i}"}).glyph(self.lx)
                  for i in range(50)}
        conv = P.Conversation([m1])
        m2 = P.Message("lexicon", "reasoner", "answer", {"subject": "a", "object": "b"},
                       reply_to=m1, thread=conv.state()).glyph(self.lx)
        known = dict(others, m1=m1)
        threads = {"t1": conv.state(), **{f"t{k}": P.Conversation([v]).state()
                                           for k, v in others.items()}}
        d = P.decode(m2, self.lx, known_msgs=known, known_threads=threads)
        self.assertEqual(d.get("reply_to"), "m1")
        self.assertEqual(d.get("thread"), "t1")
        self.assertGreater(d.fidelity, 0.99)

    def test_chunked_big_nested_content_is_exact(self):
        c = {f"r{i}": f"w{i}" for i in range(12)}
        c["inner"] = {"a": "b", "deeper": {"c": "d"}}
        m1 = P.Message("courier", "all", "ask", "x").glyph(self.lx)
        g = P.Message("courier", "all", "tell", P.chunked(c, self.lx),
                      reply_to=m1, thread=P.Conversation([m1]).state()).glyph(self.lx)
        plain = P.Message("courier", "all", "tell", c, reply_to=m1,
                          thread=P.Conversation([m1]).state()).glyph(self.lx)
        self.assertTrue(np.array_equal(g, plain), "chunking must not change the glyph")
        self.assertEqual(P.decode(g, self.lx).content, c)


    def test_similar_concept_does_not_hijack_content(self):
        # regression (live audit): a known concept sharing 2 of 3 slots with
        # the content used to win the nearest-name cleanup of the slot
        self.lx.define("near_miss", {"subject": "sandwich", "relation": "reliability",
                                     "object": "high"})
        c = {"subject": "sandwich", "relation": "reliability", "object": "12_of_12"}
        g = P.Message("reasoner", "all", "tell", c).glyph(self.lx)
        self.assertEqual(P.decode(g, self.lx).content, c)
        g2 = P.Message("reasoner", "all", "tell", "near_miss").glyph(self.lx)
        self.assertEqual(P.decode(g2, self.lx).content,
                         {"subject": "sandwich", "relation": "reliability", "object": "high"})


class Noise(unittest.TestCase):
    def setUp(self):
        self.lx = lex()
        self.rng = np.random.default_rng(1)

    def test_foreign_seed_rejected(self):
        g = P.Message("courier", "all", "tell", {"a": "b"}).glyph(lex(seed=7))
        d = P.decode(g, self.lx)
        self.assertFalse(d.valid)
        self.assertLess(abs(d.proto_sim), 0.06)

    def test_random_and_bare_rejected(self):
        r = (self.rng.integers(0, 2, P.DIM) * 2 - 1).astype(np.int8)
        self.assertFalse(P.decode(r, self.lx).valid)
        self.assertFalse(P.decode(self.lx.encode({"a": "b", "c": "d"}), self.lx).valid)

    def test_wrong_shape_rejected(self):
        self.assertFalse(P.decode(np.ones(100, dtype=np.int8), self.lx).valid)

    def test_mild_corruption_still_reads(self):
        g = P.Message("courier", "memory", "ask", {"subject": "q"}).glyph(self.lx).copy()
        g[self.rng.random(P.DIM) < 0.15] *= -1
        d = P.decode(g, self.lx)
        self.assertTrue(d.valid)
        self.assertEqual(d.get("act"), "ask")
        self.assertLess(d.fidelity, 0.8)   # corruption shows in fidelity

    def test_heavy_corruption_rejected(self):
        g = P.Message("courier", "memory", "ask", {"subject": "q"}).glyph(self.lx).copy()
        g[self.rng.random(P.DIM) < 0.45] *= -1
        self.assertFalse(P.decode(g, self.lx).valid)


class Threads(unittest.TestCase):
    def test_recent_turns_recoverable(self):
        lx = lex()
        turns = [P.Message("courier", "all", "tell", {"n": f"t{i}"}).glyph(lx) for i in range(10)]
        conv = P.Conversation(turns)
        for age in range(4):
            probe = conv.turn(age)
            sims = [P.sim(probe, t) for t in turns]
            self.assertEqual(int(np.argmax(sims)), 9 - age)

    def test_order_matters(self):
        lx = lex()
        a, b, c = (P.Message("courier", "all", "tell", w).glyph(lx) for w in "abc")
        self.assertLess(P.sim(P.Conversation([a, b, c]).state(),
                              P.Conversation([c, b, a]).state()), 0.9)  # measured 0.67: same-sender turns share 4 of 5 slots


class ChannelApp(unittest.TestCase):
    """send/resolve/threads/audit on a temp channel log."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = channel.LOG
        channel.LOG = Path(self.tmp.name) / "log.jsonl"
        self.lx = lex()

    def tearDown(self):
        channel.LOG = self.old
        self.tmp.cleanup()

    def test_conversation_on_channel(self):
        q = P.send("reasoner", "all", "ask", {"subject": "x", "relation": "is_a", "object": "?"}, lx=self.lx)
        channel.post("lexicon", "all", "a bare glyph", glyph=self.lx.encode({"k": "v"}))
        a = P.send("memory", "reasoner", "answer", {"subject": "x", "relation": "is_a", "object": "y"},
                   reply_ts=q["ts"], lx=self.lx)
        ok = P.send("reasoner", "memory", "agree", "true", reply_ts=a["ts"], lx=self.lx)
        P.send("courier", "all", "tell", {"subject": "noise"}, lx=self.lx)

        res = P.resolve(lx=self.lx)
        self.assertEqual(sum(d.valid for _, d in res), 4)
        self.assertEqual(sum(not d.valid for _, d in res), 1)
        chains = P.threads(lx=self.lx)
        self.assertEqual(chains[repr(q["ts"])], [[repr(q["ts"]), repr(a["ts"]), repr(ok["ts"])]])
        chain, g = P.conversation_of(ok["ts"], lx=self.lx)
        self.assertEqual(len(chain), 3)
        st = P.audit(lx=self.lx)
        self.assertEqual(st["mismatches"], [])
        self.assertEqual(st["reply_to"], [2, 2])
        inbox = P.inbox("memory", lx=self.lx)
        self.assertEqual({l["ts"] for l, _ in inbox}, {ok["ts"], q["ts"], P.envelopes()[-1]["ts"]})

    def test_conversation_glyph_as_content_is_recognised(self):
        q = P.send("reasoner", "all", "ask", {"subject": "a", "object": "?"}, lx=self.lx)
        a = P.send("memory", "reasoner", "answer", {"subject": "a", "object": "b"},
                   reply_ts=q["ts"], lx=self.lx)
        q2 = P.send("lexicon", "all", "ask", {"subject": "c", "object": "?"}, lx=self.lx)
        P.send("courier", "lexicon", "answer", {"subject": "c", "object": "d"},
               reply_ts=q2["ts"], lx=self.lx)
        chain, g = P.conversation_of(a["ts"], lx=self.lx)
        P.send("courier", "all", "tell", g, lx=self.lx)
        leaf, s, margin = P.which_conversation(P.envelopes()[-1]["glyph"], lx=self.lx)
        self.assertEqual(leaf, repr(a["ts"]))
        self.assertGreater(margin, 0.05)

    def test_auto_chunk_on_big_content(self):
        big = {f"r{i}": f"w{i}" for i in range(10)}
        P.send("courier", "all", "tell", big, lx=self.lx)
        (l, d), = P.resolve(lx=self.lx)
        self.assertEqual(d.content, big)


if __name__ == "__main__":
    unittest.main()
