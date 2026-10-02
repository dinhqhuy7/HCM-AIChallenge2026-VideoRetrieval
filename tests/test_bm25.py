import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.bm25 import BM25  # noqa: E402

DOCUMENTS = [["gia", "vang", "tang"], ["gia", "xang"], ["thoi", "tiet", "hom", "nay", "mua", "to"]]


class BM25Test(unittest.TestCase):
    def setUp(self):
        self.index = BM25(1.2, 0.75).build(DOCUMENTS)

    def test_score_matches_the_formula(self):
        (number, score), = self.index.search(["vang"], 3)
        idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
        average = (3 + 2 + 6) / 3
        expected = idf * 1 * (1.2 + 1) / (1 + 1.2 * (1 - 0.75 + 0.75 * 3 / average))
        self.assertEqual(number, 0)
        self.assertAlmostEqual(score, expected)

    def test_shorter_document_wins_at_equal_frequency(self):
        self.assertEqual([number for number, _ in self.index.search(["gia"], 3)], [1, 0])

    def test_only_matching_documents_come_back(self):
        self.assertEqual(self.index.search(["khong", "co"], 3), [])
        self.assertEqual(len(self.index.search(["gia", "mua"], 10)), 3)
        self.assertEqual(len(self.index.search(["gia", "mua"], 2)), 2)

    def test_a_repeated_query_word_counts_once(self):
        self.assertEqual(self.index.search(["gia", "gia"], 3), self.index.search(["gia"], 3))

    def test_round_trip_through_json(self):
        again = BM25.from_dict(json.loads(json.dumps(self.index.to_dict())))
        self.assertEqual(again.search(["gia", "vang"], 3), self.index.search(["gia", "vang"], 3))

    def test_empty_index(self):
        self.assertEqual(BM25(1.2, 0.75).build([]).search(["gia"], 3), [])


if __name__ == "__main__":
    unittest.main()
