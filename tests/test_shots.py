import importlib.util
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_TRANSNET = importlib.util.find_spec("transnetv2_pytorch") is not None


class CoverTest(unittest.TestCase):
    def setUp(self):
        from src.preprocess.shots import cover

        self.cover = cover

    def test_gaps_are_split_and_the_ends_stretched(self):
        # frames 10-11 and 21-24 belong to no scene; frames 0-1 and 31-34 lie outside the first and last
        self.assertEqual(self.cover([(2, 9), (12, 20), (25, 30)], 35), [(0, 10), (11, 22), (23, 34)])

    def test_adjacent_scenes_stay_as_they_are(self):
        self.assertEqual(self.cover([(0, 4), (5, 9)], 10), [(0, 4), (5, 9)])

    def test_no_scene_means_one_shot(self):
        self.assertEqual(self.cover([], 7), [(0, 6)])
        self.assertEqual(self.cover([(0, 3)], 0), [])

    def test_overlapping_scenes_are_refused(self):
        with self.assertRaises(ValueError):
            self.cover([(0, 10), (5, 20)], 30)

    def test_every_frame_lies_in_exactly_one_shot(self):
        random.seed(0)
        for _ in range(500):
            count, scenes, position = random.randint(1, 400), [], 0
            while position < count:
                start = position + random.randint(0, 5)
                end = start + random.randint(0, 40)
                scenes.append((start, end))
                position = end + 1 + random.randint(0, 6)
            shots = self.cover(scenes, count)
            self.assertEqual([frame for start, end in shots for frame in range(start, end + 1)], list(range(count)))


@unittest.skipUnless(HAVE_TRANSNET, "needs transnetv2-pytorch")
class TransNetScenesTest(unittest.TestCase):
    def test_a_gradual_transition_leaves_a_gap_that_cover_fills(self):
        import numpy as np
        from transnetv2_pytorch import TransNetV2

        from src.preprocess.shots import cover

        predictions = np.array([0.1] * 10 + [0.9] * 5 + [0.1] * 10)  # a five-frame dissolve at 10-14
        scenes = [tuple(map(int, scene)) for scene in TransNetV2.predictions_to_scenes(predictions, threshold=0.5)]
        self.assertEqual(scenes, [(0, 10), (15, 24)])  # frames 11-14 belong to no scene
        self.assertEqual(cover(scenes, len(predictions)), [(0, 12), (13, 24)])


if __name__ == "__main__":
    unittest.main()
