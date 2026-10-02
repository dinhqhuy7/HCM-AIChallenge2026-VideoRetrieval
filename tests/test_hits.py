import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.hits import Frame, group_by_shot  # noqa: E402


def frame(video, shot, index, score):
    return Frame(video, shot, f"{video}_{index:06d}", index, index * 40, score)


class HitsTest(unittest.TestCase):
    def test_frames_group_into_shots_in_rank_order(self):
        ranked = [frame("A", 1, 10, 0.9), frame("B", 5, 3, 0.8), frame("A", 1, 12, 0.7), frame("A", 2, 50, 0.6)]
        shots = group_by_shot(ranked)
        self.assertEqual([hit.shot for hit in shots], [("A", 1), ("B", 5), ("A", 2)])
        self.assertEqual([hit.score for hit in shots], [0.9, 0.8, 0.6])
        self.assertEqual([other.frame_index for other in shots[0].others], [12])
        self.assertEqual(shots[1].others, [])

    def test_same_shot_number_in_two_videos_is_two_shots(self):
        self.assertEqual(len(group_by_shot([frame("A", 1, 10, 0.9), frame("B", 1, 10, 0.8)])), 2)

    def test_empty(self):
        self.assertEqual(group_by_shot([]), [])

    def test_frames_cannot_change(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            frame("A", 1, 10, 0.9).score = 1.0


if __name__ == "__main__":
    unittest.main()
