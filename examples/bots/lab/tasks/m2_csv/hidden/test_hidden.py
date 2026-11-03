import unittest

from loader import load_people
from parser import parse_rows


class T(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_rows("a,b\n1,2"), [["a", "b"], ["1", "2"]])

    def test_quoted_comma(self):
        self.assertEqual(parse_rows('name,city\n"Smith, Jo",Austin\n'), [["name", "city"], ["Smith, Jo", "Austin"]])

    def test_escaped_quote_and_newline(self):
        self.assertEqual(parse_rows('q\n"he said ""hi""\nthen left"'), [["q"], ['he said "hi"\nthen left']])

    def test_empty_fields(self):
        self.assertEqual(parse_rows('a,,""\n'), [["a", "", ""]])

    def test_loader(self):
        text = 'name,age,note\n"Lee, Ann",34,"likes ""tea"""\n\nBo,7,\n'
        self.assertEqual(load_people(text), [{"name": "Lee, Ann", "age": 34, "note": 'likes "tea"'},
                                             {"name": "Bo", "age": 7, "note": ""}])
