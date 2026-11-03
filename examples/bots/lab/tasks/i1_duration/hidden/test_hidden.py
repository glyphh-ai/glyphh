import unittest

from duration import seconds


class T(unittest.TestCase):
    def test_good(self):
        self.assertEqual(seconds("45s"), 45)
        self.assertEqual(seconds("1h30m"), 5400)
        self.assertEqual(seconds("2d"), 172800)
        self.assertEqual(seconds("1d2h3m4s"), 93784)
        self.assertEqual(seconds("90m"), 5400)
        self.assertEqual(seconds("  10m "), 600)
        self.assertEqual(seconds("0s"), 0)

    def test_bad(self):
        for bad in ["", "1x", "m5", "1h1h", "5m1h", "-3s", "1.5h", "h", "1 h", "10"]:
            with self.assertRaises(ValueError, msg=bad):
                seconds(bad)
