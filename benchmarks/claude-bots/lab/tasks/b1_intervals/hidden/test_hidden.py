import unittest

from intervals import merge


class T(unittest.TestCase):
    def test_touching(self):
        self.assertEqual(merge([[1, 3], [3, 5]]), [[1, 5]])

    def test_unsorted(self):
        self.assertEqual(merge([[8, 10], [1, 3], [2, 6]]), [[1, 6], [8, 10]])

    def test_contained(self):
        self.assertEqual(merge([[1, 10], [2, 3]]), [[1, 10]])

    def test_empty(self):
        self.assertEqual(merge([]), [])

    def test_does_not_mutate(self):
        given = [[2, 3], [1, 2]]
        merge(given)
        self.assertEqual(given, [[2, 3], [1, 2]])
