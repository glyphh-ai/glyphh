import unittest

from bank import Ledger


def ledger():
    led = Ledger()
    led.open("a", overdraft=500)
    led.open("b")
    led.open("c")
    return led


class T(unittest.TestCase):
    def test_overdraft_refused_cleanly(self):
        led = ledger()
        with self.assertRaises(ValueError):
            led.transfer("a", "b", 501, "k1")
        self.assertEqual((led.balance("a"), led.balance("b")), (0, 0))
        led.transfer("a", "b", 500, "k2")
        self.assertEqual((led.balance("a"), led.balance("b")), (-500, 500))

    def test_idempotency(self):
        led = ledger()
        t1 = led.transfer("a", "b", 100, "k")
        self.assertEqual(led.transfer("a", "b", 100, "k"), t1)
        self.assertEqual(led.balance("b"), 100)
        with self.assertRaises(ValueError):
            led.transfer("a", "c", 100, "k")
        with self.assertRaises(ValueError):
            led.transfer("a", "b", 200, "k")

    def test_bad_transfers(self):
        led = ledger()
        for args in [("a", "a", 10), ("a", "b", 0), ("a", "b", -5)]:
            with self.assertRaises(ValueError):
                led.transfer(*args, key=f"x{args}")
        self.assertEqual(led.entries, [])

    def test_reverse_once_even_below_zero(self):
        led = ledger()
        tid = led.transfer("a", "b", 300, "k")
        led.transfer("b", "c", 300, "k2")
        rid = led.reverse(tid)
        self.assertEqual((led.balance("a"), led.balance("b"), led.balance("c")), (0, -300, 300))
        with self.assertRaises(ValueError):
            led.reverse(tid)
        with self.assertRaises(ValueError):
            led.reverse(rid)

    def test_failed_key_reusable(self):
        led = ledger()
        with self.assertRaises(ValueError):
            led.transfer("b", "c", 1, "k")
        led.transfer("a", "c", 1, "k")
        self.assertEqual(led.balance("c"), 1)
