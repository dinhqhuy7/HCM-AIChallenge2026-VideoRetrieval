import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fusion.shaping import ResultShaper, VideoSpread  # noqa: E402
from src.retrieval.hits import Frame, ShotHit  # noqa: E402


def frame(video, index, shot=0):
    return Frame(video, shot, f"{video}_{index:06d}", index, index * 40)


def hit(video, shot, index, others=()):
    return ShotHit(frame(video, index, shot), 1.0 / (shot + 1), [frame(video, other, shot) for other in others])


class VideoSpreadTest(unittest.TestCase):
    def test_the_head_is_kept_and_the_tail_goes_round_the_videos(self):
        frames = [frame("A", 1), frame("A", 2), frame("A", 3), frame("B", 4), frame("C", 5), frame("B", 6)]
        spread = VideoSpread(keep_top=2, per_video=1).apply(frames)
        self.assertEqual([f.keyframe_id for f in spread],
                         ["A_000001", "A_000002", "A_000003", "B_000004", "C_000005", "B_000006"])

    def test_two_rows_of_each_video_in_turn(self):
        frames = [frame("A", i) for i in range(5)] + [frame("B", 9)]
        spread = VideoSpread(keep_top=0, per_video=2).apply(frames)
        self.assertEqual([(f.video_id, f.frame_index) for f in spread],
                         [("A", 0), ("A", 1), ("B", 9), ("A", 2), ("A", 3), ("A", 4)])

    def test_it_only_reorders(self):
        frames = [frame("A", 1), frame("B", 2), frame("A", 3)]
        self.assertCountEqual(VideoSpread(1, 1).apply(frames), frames)
        self.assertEqual(VideoSpread(10, 1).apply(frames), frames)  # a head longer than the list
        self.assertEqual(VideoSpread(0, 1).apply([]), [])

    def test_the_numbers_are_checked(self):
        for keep_top, per_video in ((-1, 1), (0, 0)):
            with self.assertRaisesRegex(ValueError, "keep_top >= 0 and per_video >= 1"):
                VideoSpread(keep_top, per_video)


class ResultShaperTest(unittest.TestCase):
    def test_one_row_per_shot_then_the_spare_frames(self):
        shots = [hit("A", 0, 10, others=(11, 12)), hit("A", 1, 20), hit("B", 2, 30, others=(31,))]
        rows = ResultShaper(10).shape(shots)
        self.assertEqual([f.keyframe_id for f in rows],
                         ["A_000010", "A_000020", "B_000030", "A_000011", "A_000012", "B_000031"])

    def test_the_rows_are_cut_and_the_spread_reorders_the_shot_rows_only(self):
        shots = [hit("A", 0, 10, others=(11,)), hit("A", 1, 20), hit("B", 2, 30)]
        self.assertEqual([f.frame_index for f in ResultShaper(2).shape(shots)], [10, 20])
        rows = ResultShaper(4, VideoSpread(keep_top=1, per_video=1)).shape(shots)
        self.assertEqual([f.frame_index for f in rows], [10, 20, 30, 11])

    def test_no_shots_no_rows_and_rows_are_checked(self):
        self.assertEqual(ResultShaper(5).shape([]), [])
        with self.assertRaisesRegex(ValueError, "rows must be 1 or more"):
            ResultShaper(0)


if __name__ == "__main__":
    unittest.main()
