import unittest

from limiter import TokenBucket


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class T(unittest.TestCase):
    def test_burst_then_refuse(self):
        c = Clock()
        b = TokenBucket(rate=2, burst=3, clock=c)
        self.assertEqual([b.allow() for _ in range(4)], [True, True, True, False])

    def test_refusal_takes_nothing(self):
        c = Clock()
        b = TokenBucket(rate=1, burst=2, clock=c)
        self.assertTrue(b.allow(2))
        self.assertFalse(b.allow(1))
        c.t += 0.5
        self.assertFalse(b.allow(1))
        c.t += 0.5
        self.assertTrue(b.allow(1))

    def test_fractional_refill_and_cap(self):
        c = Clock()
        b = TokenBucket(rate=2, burst=3, clock=c)
        for _ in range(3):
            b.allow()
        c.t += 0.25
        self.assertFalse(b.allow())
        c.t += 0.25
        self.assertTrue(b.allow())
        c.t += 1000
        self.assertEqual([b.allow() for _ in range(4)], [True, True, True, False])

    def test_retry_after(self):
        c = Clock()
        b = TokenBucket(rate=4, burst=4, clock=c)
        self.assertEqual(b.retry_after(4), 0)
        b.allow(4)
        self.assertAlmostEqual(b.retry_after(2), 0.5)
        with self.assertRaises(ValueError):
            b.retry_after(5)
