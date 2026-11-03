import unittest
from datetime import datetime as D

from cron import next_run


class T(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(next_run("*/15 * * * *", D(2026, 1, 1, 10, 7, 30)), D(2026, 1, 1, 10, 15))
        self.assertEqual(next_run("0 9 * * *", D(2026, 1, 1, 9, 0)), D(2026, 1, 2, 9, 0))
        self.assertEqual(next_run("30 23 31 12 *", D(2026, 12, 31, 23, 30)), D(2027, 12, 31, 23, 30))

    def test_ranges_lists_steps(self):
        self.assertEqual(next_run("10-30/10 8,17 * * *", D(2026, 3, 3, 8, 31)), D(2026, 3, 3, 17, 10))
        self.assertEqual(next_run("0 0 1 jan,Jul *", D(2026, 2, 1)), D(2026, 7, 1))

    def test_dow(self):
        # 2026-11-03 is a Tuesday
        self.assertEqual(next_run("0 12 * * MON-FRI", D(2026, 11, 6, 12, 0)), D(2026, 11, 9, 12, 0))
        self.assertEqual(next_run("0 0 * * 7", D(2026, 11, 3)), D(2026, 11, 8))
        self.assertEqual(next_run("0 0 * * sun", D(2026, 11, 3)), D(2026, 11, 8))

    def test_dom_or_dow(self):
        # restricted day-of-month OR restricted day-of-week
        self.assertEqual(next_run("0 0 13 * FRI", D(2026, 11, 3)), D(2026, 11, 6))
        self.assertEqual(next_run("0 0 4 * FRI", D(2026, 11, 3)), D(2026, 11, 4))

    def test_rare(self):
        self.assertEqual(next_run("0 0 29 2 *", D(2026, 3, 1)), D(2028, 2, 29))

    def test_invalid(self):
        for bad in ["* * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8", "*/0 * * * *",
                    "a * * * *", "5-1 * * * *", "* * * FOO *"]:
            with self.assertRaises(ValueError, msg=bad):
                next_run(bad, D(2026, 1, 1))
