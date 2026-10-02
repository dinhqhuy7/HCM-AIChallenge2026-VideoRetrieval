import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.hits import Frame  # noqa: E402
from src.retrieval.lanes import KeywordLane, VisualLane  # noqa: E402


class FakeEncoder:
    def __init__(self):
        self.texts = []

    def encode_texts(self, texts):
        import numpy as np

        self.texts += texts
        return np.zeros((len(texts), 4), dtype=np.float32)


class FakeIndex:
    """Frames ranked best first; the search returns the first ``limit`` of them."""

    MAX_LIMIT = 8

    def __init__(self, frames):
        self.frames = frames
        self.limits = []

    def search(self, vector, limit, video_id=None):
        self.limits.append(limit)
        return self.frames[:limit]


def frames(shots_per_frame):
    return [Frame("V", shot, f"V_{number:06d}", number, number * 40, 1.0 - number / 100)
            for number, shot in enumerate(shots_per_frame)]


class VisualLaneTest(unittest.TestCase):
    def lane(self, shots_per_frame, translate=None):
        self.encoder, self.index = FakeEncoder(), FakeIndex(frames(shots_per_frame))
        return VisualLane(self.encoder, self.index, translate)

    def test_the_frame_search_widens_until_it_covers_enough_shots(self):
        lane = self.lane([0, 0, 0, 0, 1, 2, 3, 3])  # four frames of shot 0 crowd out the rest
        shots = lane.search("cảnh đường phố", 3)
        self.assertEqual([hit.shot for hit in shots], [("V", 0), ("V", 1), ("V", 2)])
        self.assertEqual(self.index.limits, [3, 6])  # the first 3 frames held one shot, 6 hold three
        self.assertEqual([f.frame_index for f in shots[0].others], [1, 2, 3])

    def test_it_stops_when_the_index_runs_out(self):
        lane = self.lane([0, 0, 0])
        self.assertEqual([hit.shot for hit in lane.search("gì đó", 4)], [("V", 0)])
        self.assertEqual(self.index.limits, [4])  # fewer frames came back than asked: no point widening

    def test_it_stops_at_the_limit_of_the_index(self):
        lane = self.lane([0] * 8)
        self.assertEqual(len(lane.search("gì đó", 5)), 1)
        self.assertEqual(self.index.limits, [5, 8])  # 10 would pass MAX_LIMIT, so 8

    def test_the_query_is_translated_before_it_is_encoded(self):
        lane = self.lane([0, 1], translate=lambda text: f"english of {text}")
        lane.search("một người đàn ông", 2)
        self.assertEqual(self.encoder.texts, ["english of một người đàn ông"])
        plain = self.lane([0, 1])
        plain.search("một người đàn ông", 2)
        self.assertEqual(self.encoder.texts, ["một người đàn ông"])

    def test_no_depth_no_search(self):
        lane = self.lane([0, 1])
        self.assertEqual(lane.search("gì đó", 0), [])
        self.assertEqual(self.index.limits, [])


class FakeKeywordIndex:
    lane = "ocr"

    def __init__(self):
        self.asked = []

    def search(self, query, limit):
        self.asked.append((query, limit))
        return ["hit"] * limit


class KeywordLaneTest(unittest.TestCase):
    def test_it_takes_its_name_from_the_index_and_passes_the_depth(self):
        index = FakeKeywordIndex()
        lane = KeywordLane(index)
        self.assertEqual((lane.name, len(lane.search("giá vàng", 5))), ("ocr", 5))
        self.assertEqual(index.asked, [("giá vàng", 5)])
        self.assertEqual(lane.search("giá vàng", 0), [])


if __name__ == "__main__":
    unittest.main()
