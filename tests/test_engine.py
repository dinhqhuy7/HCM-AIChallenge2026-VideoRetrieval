import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import MissingSetting  # noqa: E402
from src.fusion.rank_fusion import ReciprocalRankFusion  # noqa: E402
from src.fusion.shaping import ResultShaper  # noqa: E402
from src.retrieval.engine import SearchEngine  # noqa: E402
from src.retrieval.hits import Frame, ShotHit  # noqa: E402


def hit(shot, index, others=()):
    frame = Frame("V", shot, f"V_{index:06d}", index, index * 40, 1.0)
    return ShotHit(frame, 1.0, [Frame("V", shot, f"V_{other:06d}", other, other * 40) for other in others])


class FakeLane:
    def __init__(self, name, hits):
        self.name, self.hits = name, hits
        self.asked = []

    def search(self, query, depth):
        self.asked.append((query, depth))
        return self.hits[:depth]


class SearchEngineTest(unittest.TestCase):
    def setUp(self):
        self.visual = FakeLane("visual", [hit(1, 10, others=(11,)), hit(2, 20), hit(3, 30)])
        self.ocr = FakeLane("ocr", [hit(3, 31), hit(1, 12), hit(4, 40)])
        self.lanes = {"visual": self.visual, "ocr": self.ocr}

    def engine(self, fusion=ReciprocalRankFusion(60), rows=10, depth=5):
        return SearchEngine(self.lanes, fusion, ResultShaper(rows), depth)

    def test_one_box_answers_on_its_own(self):
        rows = self.engine(fusion=None).search({"visual": "cảnh đường phố", "ocr": "  "})
        self.assertEqual([frame.keyframe_id for frame in rows], ["V_000010", "V_000020", "V_000030", "V_000011"])
        self.assertEqual((self.visual.asked, self.ocr.asked), ([("cảnh đường phố", 5)], []))

    def test_two_boxes_are_combined_and_every_lane_is_asked(self):
        rows = self.engine().search({"visual": "đường phố", "ocr": "giá vàng"})
        self.assertEqual((self.visual.asked, self.ocr.asked), ([("đường phố", 5)], [("giá vàng", 5)]))
        # shot 1 (ranks 1 and 2) and shot 3 (3 and 1) come first, then shot 2 and shot 4
        self.assertEqual([frame.shot_id for frame in rows[:4]], [1, 3, 2, 4])

    def test_the_rows_are_shaped_and_cut(self):
        rows = self.engine(rows=2).search({"visual": "đường phố"})
        self.assertEqual([frame.keyframe_id for frame in rows], ["V_000010", "V_000020"])

    def test_an_empty_query_is_refused(self):
        for queries in ({}, {"visual": ""}, {"visual": "   ", "ocr": None}):
            with self.assertRaisesRegex(ValueError, "type something into at least one box"):
                self.engine().search(queries)

    def test_a_box_with_no_lane_says_which_lanes_there_are(self):
        with self.assertRaisesRegex(ValueError, r"no lane for \['asr'\]; this index has \['ocr', 'visual'\]"):
            self.engine().search({"asr": "xin chào"})

    def test_combining_without_a_k_names_the_setting(self):
        with self.assertRaisesRegex(MissingSetting, r"set `fusion.rrf_k`"):
            self.engine(fusion=None).search({"visual": "đường phố", "ocr": "giá vàng"})


if __name__ == "__main__":
    unittest.main()
