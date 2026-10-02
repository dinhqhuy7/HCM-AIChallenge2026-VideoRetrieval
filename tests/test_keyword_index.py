import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.keyword_index import KeywordIndex, Line, ShotDocument  # noqa: E402


def line(text, index):
    return Line(text, f"V1_{index:06d}", index, index * 40)


class KeywordIndexTest(unittest.TestCase):
    def setUp(self):
        self.documents = [
            ShotDocument("V1", 0, [line("HTV", 10), line("Giá vàng", 20), line("Giá vàng tăng mạnh", 30)]),
            ShotDocument("V1", 1, [line("Thời tiết hôm nay", 60)]),
            ShotDocument("V1", 2, []),
        ]
        self.index = KeywordIndex.build("ocr", self.documents, 1.2, 0.75)

    def test_the_hit_stands_on_the_keyframe_with_the_most_query_words(self):
        (hit,) = self.index.search("giá vàng tăng", 10)
        self.assertEqual((hit.shot, hit.frame.keyframe_id, hit.frame.time_ms), (("V1", 0), "V1_000030", 1200))
        self.assertEqual(hit.frame.score, hit.score)

    def test_a_tie_goes_to_the_earlier_keyframe(self):
        (hit,) = self.index.search("giá vàng", 10)
        self.assertEqual(hit.frame.keyframe_id, "V1_000020")

    def test_marks_do_not_matter(self):
        self.assertEqual(self.index.search("GIA VANG", 10)[0].frame, self.index.search("giá vàng", 10)[0].frame)

    def test_shots_without_lines_are_left_out(self):
        self.assertEqual([(d.video_id, d.shot_id) for d in self.index.documents], [("V1", 0), ("V1", 1)])
        self.assertEqual(self.index.search("không có", 10), [])

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "keywords-ocr.json"
            self.index.save(path)
            again = KeywordIndex.load(path)
        self.assertEqual(again.lane, "ocr")
        self.assertEqual([(h.shot, h.frame, h.score) for h in again.search("thời tiết", 10)],
                         [(h.shot, h.frame, h.score) for h in self.index.search("thời tiết", 10)])


if __name__ == "__main__":
    unittest.main()
