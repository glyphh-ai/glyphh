import unittest

from text import slugify


class T(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify("Hello, World!"), "hello-world")
        self.assertEqual(slugify("  Many   spaces -- here "), "many-spaces-here")

    def test_accents(self):
        self.assertEqual(slugify("Café Crème"), "cafe-creme")
        self.assertEqual(slugify("Straße"), "strasse")

    def test_apostrophe(self):
        self.assertEqual(slugify("Don't Stop"), "dont-stop")

    def test_max_len(self):
        self.assertEqual(slugify("alpha beta gamma", max_len=12), "alpha-beta")
        self.assertEqual(slugify("supercalifragilistic", max_len=5), "super")
        self.assertEqual(slugify("ab cd", max_len=5), "ab-cd")
