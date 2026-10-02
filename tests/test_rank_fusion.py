import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fusion.rank_fusion import ReciprocalRankFusion  # noqa: E402
from src.retrieval.hits import Frame, ShotHit  # noqa: E402


def hit(video, shot, score, keyframe=0, others=()):
    frame = Frame(video, shot, f"{video}_{keyframe:06d}", keyframe, keyframe * 40, score)
    return ShotHit(frame, score, [Frame(video, shot, f"{video}_{index:06d}", index, index * 40) for index in others])


class ReciprocalRankFusionTest(unittest.TestCase):
    def setUp(self):
        self.fusion = ReciprocalRankFusion(60)

    def test_k_is_required_and_cannot_be_negative(self):
        for bad in (None, -1):
            with self.assertRaisesRegex(ValueError, "the paper uses 60"):
                ReciprocalRankFusion(bad)
        self.assertEqual(ReciprocalRankFusion(0).k, 0.0)

    def test_one_ranking_keeps_its_order_and_scores_by_rank(self):
        fused = self.fusion.fuse([[hit("V", 2, 0.9), hit("V", 1, 0.5), hit("V", 3, 0.1)]])
        self.assertEqual([shot.shot for shot in fused], [("V", 2), ("V", 1), ("V", 3)])
        self.assertAlmostEqual(fused[0].score, 1 / 61)
        self.assertAlmostEqual(fused[2].score, 1 / 63)

    def test_two_lanes_agreeing_beat_one_lane_leading(self):
        visual = [hit("V", 1, 0.9), hit("V", 2, 0.8), hit("V", 3, 0.7)]
        speech = [hit("V", 4, 12.0), hit("V", 2, 9.0), hit("V", 3, 8.0)]
        fused = self.fusion.fuse([visual, speech])
        self.assertEqual([shot.shot for shot in fused[:2]], [("V", 2), ("V", 3)])
        self.assertAlmostEqual(fused[0].score, 1 / 62 + 1 / 62)
        self.assertAlmostEqual(fused[2].score, 1 / 61)  # V1 and V4 lead one list each

    def test_a_tie_goes_to_the_better_rank_then_to_the_shot(self):
        first = [hit("B", 1, 0.9), hit("A", 9, 0.8)]
        second = [hit("A", 9, 5.0), hit("B", 1, 4.0)]
        fused = self.fusion.fuse([first, second])
        self.assertEqual([shot.shot for shot in fused], [("A", 9), ("B", 1)])  # same score, both rank 1
        # exactly equal, not equal after rounding: the shares are added in the same order for both
        self.assertEqual(fused[0].score, fused[1].score)
        self.assertAlmostEqual(fused[0].score, 1 / 61 + 1 / 62)

    def test_a_shot_keeps_the_frames_of_the_list_that_ranked_it_highest(self):
        weak = [hit("V", 0, 0.1, keyframe=7, others=(8,)), hit("V", 1, 0.9, keyframe=1)]
        strong = [hit("V", 1, 5.0, keyframe=2, others=(3, 4))]
        (top, second) = self.fusion.fuse([weak, strong])
        self.assertEqual((top.shot, top.frame.keyframe_id, [f.frame_index for f in top.others]), (("V", 1), "V_000002",
                                                                                                  [3, 4]))
        self.assertEqual((second.frame.keyframe_id, [f.frame_index for f in second.others]), ("V_000007", [8]))

    def test_nothing_in_nothing_out(self):
        self.assertEqual(self.fusion.fuse([]), [])
        self.assertEqual(self.fusion.fuse([[], []]), [])


if __name__ == "__main__":
    unittest.main()
