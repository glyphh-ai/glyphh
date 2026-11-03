import unittest

from jobqueue import Queue
from stats import summary
from worker import run_once


def boom(payload):
    raise RuntimeError(payload.get("msg", "boom"))


class T(unittest.TestCase):
    def test_backoff_and_dead(self):
        q = Queue(base=10, max_attempts=3)
        jid = q.push("x", {"msg": "bad"})
        run_once(q, {"x": boom}, now=0)
        self.assertEqual(q.jobs[0].due, 10)
        self.assertIsNone(run_once(q, {"x": boom}, now=5))
        run_once(q, {"x": boom}, now=10)
        self.assertEqual(q.jobs[0].due, 30)
        run_once(q, {"x": boom}, now=30)
        self.assertEqual(q.jobs, [])
        self.assertEqual([(j.id, j.error) for j in q.dead_letters], [(jid, "bad")])

    def test_own_max_attempts(self):
        q = Queue(base=1, max_attempts=5)
        q.push("x", {}, max_attempts=1)
        run_once(q, {"x": boom}, now=0)
        self.assertEqual(len(q.dead_letters), 1)

    def test_order_and_ties(self):
        q = Queue()
        a = q.push("x", {}, due=5)
        b = q.push("x", {}, due=1)
        c = q.push("x", {}, due=1)
        self.assertEqual([q.next(10).id], [b])
        q.done(b)
        self.assertEqual(q.next(10).id, c)
        q.done(c)
        self.assertEqual(q.next(10).id, a)

    def test_no_handler_and_stats(self):
        q = Queue(base=100)
        q.push("missing", {})
        q.push("ok", {})
        q.push("x", {})
        q.push("later", {}, due=50)
        run_once(q, {"ok": lambda p: None, "x": boom}, now=0)
        run_once(q, {"ok": lambda p: None, "x": boom}, now=0)
        run_once(q, {"ok": lambda p: None, "x": boom}, now=0)
        self.assertEqual(q.dead_letters[0].error, "no handler")
        self.assertEqual(summary(q, now=0), {"pending": 2, "waiting": 2, "dead": 1, "done": 1})
