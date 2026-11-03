import re
import unittest
from pathlib import Path

from expr import evaluate


class T(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(evaluate("1 + 2 * 3"), 7)
        self.assertEqual(evaluate("(1 + 2) * 3"), 9)
        self.assertEqual(evaluate("2 ** 3 ** 2"), 512)
        self.assertEqual(evaluate("-2 ** 2"), -4)
        self.assertEqual(evaluate("2 ** -1"), 0.5)
        self.assertEqual(evaluate("10 - 4 - 3"), 3)
        self.assertEqual(evaluate("7 % 3 * 2"), 2)
        self.assertEqual(evaluate("--3"), 3)

    def test_types(self):
        self.assertIsInstance(evaluate("6 * 7"), int)
        self.assertEqual(evaluate("7 / 2"), 3.5)
        self.assertEqual(evaluate(".5 + 2.5"), 3.0)

    def test_vars_funcs(self):
        self.assertEqual(evaluate("max(a, b * 2, 3) + abs(-c)", {"a": 1, "b": 4, "c": 2}), 10)
        self.assertEqual(evaluate("min( x_1 , 10 )", {"x_1": 3}), 3)

    def test_errors(self):
        for bad in ["1 +", "(1", "1)", "2 3", "foo(1)", "abs(1, 2)", "max()", "y + 1", "1 ** ", "", "3..2"]:
            with self.assertRaises(ValueError, msg=bad):
                evaluate(bad)
        for bad in ["1 / 0", "5 % (2 - 2)"]:
            with self.assertRaises(ZeroDivisionError, msg=bad):
                evaluate(bad)

    def test_no_eval(self):
        src = Path(__file__).with_name("expr.py").read_text()
        for word in ["eval", "exec", "compile"]:
            self.assertIsNone(re.search(rf"(?<![\w.]){word}\s*\(", src), word)
