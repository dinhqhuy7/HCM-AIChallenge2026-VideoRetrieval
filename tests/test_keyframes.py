import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_YAML = importlib.util.find_spec("yaml") is not None


@unittest.skipUnless(HAVE_YAML, "needs PyYAML")
class KeyframePolicyTest(unittest.TestCase):
    def setUp(self):
        from src.config import MissingSetting, Settings
        from src.preprocess.keyframes import DenseFrames, MiddleFrame, keyframe_policy

        self.MissingSetting, self.Settings = MissingSetting, Settings
        self.DenseFrames, self.MiddleFrame, self.keyframe_policy = DenseFrames, MiddleFrame, keyframe_policy

    def test_middle(self):
        (slot,) = self.MiddleFrame().slots(3, 10, 21)
        self.assertEqual((slot.shot_id, slot.candidates), (3, range(15, 16)))

    def test_dense_slots_are_centred_and_do_not_overlap(self):
        slots = self.DenseFrames(5, 2).slots(0, 0, 11)
        self.assertEqual([slot.candidates for slot in slots], [range(1, 6), range(6, 11)])
        self.assertEqual([slot.candidates for slot in self.DenseFrames(5, 0).slots(0, 100, 124)],
                         [range(102, 103), range(107, 108), range(112, 113), range(117, 118), range(122, 123)])

    def test_the_documented_spacing_bounds_hold_and_are_reached(self):
        """docs/offline/01-shots-and-keyframes.md: neighbours are at most gap + 2r apart inside a shot, 2 gap - 1 + 2r
        across a cut; up to gap - 1 + r frames lie before the first keyframe and after the last."""
        import random

        rng = random.Random(7)
        for gap, radius in ((1, 0), (5, 2), (10, 4), (25, 12)):
            policy = self.DenseFrames(gap, radius)
            lengths = [rng.randint(1, 6 * gap) for _ in range(400)]
            lengths[0] = lengths[-1] = 2 * gap - 1  # the length that leaves the most frames before and after
            shots, start = [], 0
            for length in lengths:
                shots.append((start, start + length - 1))
                start += length
            slots = [slot for shot_id, (first, last) in enumerate(shots) for slot in policy.slots(shot_id, first, last)]
            frames = [frame for slot in slots for frame in slot.candidates]
            self.assertEqual(len(frames), len(set(frames)))  # no two slots share a frame
            within = [b.candidates[-1] - a.candidates[0] for a, b in zip(slots, slots[1:]) if a.shot_id == b.shot_id]
            across = [b.candidates[-1] - a.candidates[0] for a, b in zip(slots, slots[1:]) if a.shot_id != b.shot_id]
            self.assertEqual((max(within), max(across)), (gap + 2 * radius, 2 * gap - 1 + 2 * radius))
            self.assertEqual((slots[0].candidates[-1], shots[-1][1] - slots[-1].candidates[0]),
                             (gap - 1 + radius,) * 2)

    def test_a_short_shot_gets_one_slot(self):
        self.assertEqual([slot.candidates for slot in self.DenseFrames(5, 2).slots(0, 20, 22)], [range(20, 23)])
        self.assertEqual([slot.candidates for slot in self.DenseFrames(5, 2).slots(0, 7, 7)], [range(7, 8)])

    def test_slots_that_would_share_a_frame_are_refused(self):
        for gap, radius in ((4, 2), (0, 0), (5, -1)):
            with self.assertRaises(ValueError):
                self.DenseFrames(gap, radius)

    def test_policy_from_settings(self):
        settings = self.Settings({"keyframes": {"policy": "dense", "dense": {"frame_gap": 8, "search_radius": 1}}})
        policy = self.keyframe_policy(settings)
        self.assertEqual((policy.frame_gap, policy.search_radius), (8, 1))
        self.assertIsInstance(self.keyframe_policy(self.Settings({})), self.MiddleFrame)

    def test_dense_needs_both_numbers(self):
        with self.assertRaises(self.MissingSetting):
            self.keyframe_policy(self.Settings({"keyframes": {"policy": "dense", "dense": {"frame_gap": None}}}))
        with self.assertRaises(ValueError):
            self.keyframe_policy(self.Settings({"keyframes": {"policy": "every-frame"}}))


if __name__ == "__main__":
    unittest.main()
