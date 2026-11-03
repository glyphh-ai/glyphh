import unittest

from semver import compare

ORDER = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
         "1.0.0-rc.1", "1.0.0", "1.0.1", "1.1.0", "2.0.0", "10.0.0"]


class T(unittest.TestCase):
    def test_order(self):
        for i, a in enumerate(ORDER):
            for j, b in enumerate(ORDER):
                self.assertEqual(compare(a, b), (i > j) - (i < j), f"{a} vs {b}")

    def test_build_ignored(self):
        self.assertEqual(compare("1.0.0+build.1", "1.0.0+other"), 0)
        self.assertEqual(compare("1.0.0-alpha+x", "1.0.0-alpha"), 0)

    def test_invalid(self):
        for bad in ["1.0", "01.0.0", "1.0.0-", "1.0.0-01", "a.b.c", "", "1.0.0.0"]:
            with self.assertRaises(ValueError, msg=bad):
                compare(bad, "1.0.0")
