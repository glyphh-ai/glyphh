import unittest

from inventory import Inventory
from report import summary


def inv():
    i = Inventory()
    i.add("apple", 5)
    i.add("pear", 2)
    return i


class T(unittest.TestCase):
    def test_reserve(self):
        i = inv()
        i.reserve("apple", 3)
        self.assertEqual(i.available("apple"), 2)
        i.release("apple", 1)
        self.assertEqual(i.available("apple"), 3)

    def test_limits(self):
        i = inv()
        with self.assertRaises(ValueError):
            i.reserve("pear", 3)
        i.reserve("pear", 2)
        with self.assertRaises(ValueError):
            i.release("pear", 3)
        with self.assertRaises(ValueError):
            i.remove("pear", 1)

    def test_summary(self):
        i = inv()
        i.reserve("pear", 2)
        i.reserve("apple", 1)
        self.assertEqual(summary(i), "apple: 5 in stock, 1 reserved, 4 available\n"
                                     "pear: 2 in stock, 2 reserved, 0 available\nOut: pear")

    def test_summary_plain(self):
        self.assertEqual(summary(inv()), "apple: 5 in stock, 0 reserved, 5 available\n"
                                         "pear: 2 in stock, 0 reserved, 2 available")
