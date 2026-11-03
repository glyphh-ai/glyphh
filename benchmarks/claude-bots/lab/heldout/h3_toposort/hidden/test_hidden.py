import unittest

from topo import CycleError, order


class T(unittest.TestCase):
    def test_order(self):
        self.assertEqual(order({"deploy": ["build", "test"], "test": ["build"], "build": []}), ["build", "test", "deploy"])

    def test_alphabetical_ties_and_implicit(self):
        self.assertEqual(order({"d": ["b", "a"], "c": []}), ["a", "b", "c", "d"])

    def test_empty(self):
        self.assertEqual(order({}), [])

    def test_cycle(self):
        with self.assertRaises(CycleError) as e:
            order({"a": ["b"], "b": ["c"], "c": ["a"], "x": []})
        self.assertTrue(issubclass(CycleError, ValueError))
        self.assertEqual(e.exception.cycle, ["a", "b", "c", "a"])

    def test_self_cycle(self):
        with self.assertRaises(CycleError) as e:
            order({"q": ["q"]})
        self.assertEqual(e.exception.cycle, ["q", "q"])
