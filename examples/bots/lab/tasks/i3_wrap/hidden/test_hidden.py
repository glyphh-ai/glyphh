import unittest

from wrap import wrap


class T(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(wrap("the quick brown fox", 10), "the quick\nbrown fox")

    def test_exact(self):
        self.assertEqual(wrap("aaaa bbbb", 4), "aaaa\nbbbb")

    def test_spaces(self):
        self.assertEqual(wrap("a    b   c", 3), "a b\nc")

    def test_long_word(self):
        self.assertEqual(wrap("abcdefghij xy", 4), "abcd\nefgh\nij\nxy")

    def test_paragraphs(self):
        self.assertEqual(wrap("one two\nthree\n\n\nfour", 9), "one two\nthree\n\nfour")
