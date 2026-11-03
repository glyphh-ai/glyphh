import unittest
from decimal import Decimal

from cart import Cart
from tax import tax


class T(unittest.TestCase):
    def test_half_up(self):
        self.assertEqual(tax(Decimal("1.00"), "general"), Decimal("0.08"))
        self.assertEqual(tax(Decimal("10.00"), "food"), Decimal("0.63"))  # 0.625 rounds up

    def test_total(self):
        c = Cart()
        c.add("19.99", 3)
        c.add("10.00", 1, "food")
        self.assertEqual(c.total(), Decimal("75.55"))  # 59.97 + 4.95 + 10.00 + 0.63 (0.625 half up)
        self.assertIsInstance(c.total(), Decimal)
        self.assertEqual(c.total().as_tuple().exponent, -2)

    def test_many_small(self):
        c = Cart()
        for _ in range(10):
            c.add("0.10", 1, "food")
        self.assertEqual(c.total(), Decimal("1.10"))  # each line 0.10 + 0.01 (0.00625 rounds to 0.01)
