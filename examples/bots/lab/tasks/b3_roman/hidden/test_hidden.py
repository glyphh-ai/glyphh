import unittest

from roman import parse


class T(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse("III"), 3)
        self.assertEqual(parse("LVIII"), 58)

    def test_subtractive(self):
        self.assertEqual(parse("IX"), 9)
        self.assertEqual(parse("XL"), 40)
        self.assertEqual(parse("MCMXCIV"), 1994)
        self.assertEqual(parse("MMMCMXCIX"), 3999)

    def test_invalid(self):
        for bad in ["IIII", "VV", "IC", "", "XM", "MMMM", "ABC", "IIV"]:
            with self.assertRaises(ValueError, msg=bad):
                parse(bad)
