import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("numpy", "PIL", "cv2", "yaml"))


def keyframe(hash_, sharpness, rejected=None):
    return {"dhash": hash_, "sharpness": sharpness, "rejected": rejected}


@unittest.skipUnless(HAVE_LIBRARIES, "needs numpy, Pillow, OpenCV and PyYAML")
class QualityTest(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from PIL import Image

        from src import config
        from src.preprocess import quality

        self.np, self.Image, self.config, self.q = np, Image, config, quality

    def picture(self, pixels):
        return self.Image.fromarray(self.np.asarray(pixels, dtype=self.np.uint8))

    def test_measurements(self):
        black = self.q.measure(self.picture(self.np.zeros((36, 64, 3))))
        white = self.q.measure(self.picture(self.np.full((36, 64, 3), 255)))
        noise = self.q.measure(self.picture(self.np.random.default_rng(0).integers(0, 256, (36, 64, 3))))
        self.assertEqual((black["sharpness"], black["brightness"], black["entropy"]), (0.0, 0.0, 0.0))
        self.assertEqual((white["brightness"], white["entropy"]), (255.0, 0.0))
        self.assertEqual(str(black["entropy"]), "0.0")  # not "-0.0", which is what a one-colour picture would print
        self.assertGreater(noise["entropy"], 7.0)
        self.assertGreater(noise["sharpness"], 1000.0)

    def test_thresholds_give_the_reason(self):
        limits = {"min_brightness": 10, "max_brightness": 245, "min_entropy": None}
        gate = self.q.Thresholds(self.config.Settings(limits))
        self.assertEqual(gate.reason({"sharpness": 5, "brightness": 3, "entropy": 1}), "dark")
        self.assertEqual(gate.reason({"sharpness": 5, "brightness": 250, "entropy": 1}), "bright")
        self.assertIsNone(gate.reason({"sharpness": 5, "brightness": 120, "entropy": 0}))  # entropy is not checked
        self.assertIsNone(self.q.KeepAll().reason({"sharpness": 0, "brightness": 0, "entropy": 0}))
        with self.assertRaises(ValueError):
            self.q.Thresholds(self.config.Settings({}))

    def test_dhash(self):
        picture = self.picture(self.np.random.default_rng(1).integers(0, 256, (90, 160, 3)))
        self.assertEqual(len(self.q.dhash(picture)), 16)
        self.assertEqual(self.q.hamming(self.q.dhash(picture), self.q.dhash(picture.copy())), 0)
        self.assertEqual(self.q.hamming("ff", "0f"), 4)

    def test_near_duplicates(self):
        frames = [keyframe("0000", 1), keyframe("0001", 5), keyframe("ffff", 2, "blur"), keyframe("00ff", 3)]
        self.assertEqual(self.q.NearDuplicates(1).assign(frames, 7), 9)
        self.assertEqual([frame["group"] for frame in frames], [7, 7, None, 8])
        self.assertEqual([frame["indexed"] for frame in frames], [False, True, False, True])  # sharpest per group

    def test_each_frame_alone(self):
        frames = [keyframe("0", 1), keyframe("0", 5), keyframe("0", 2, "dark"), keyframe("0", 3)]
        self.assertEqual(self.q.EachFrameAlone().assign(frames, 0), 3)
        self.assertEqual([frame["group"] for frame in frames], [0, 1, None, 2])
        self.assertEqual([frame["indexed"] for frame in frames], [True, True, False, True])

    def test_settings_pick_the_classes(self):
        Settings = self.config.Settings
        self.assertIsInstance(self.q.quality_gate(Settings({})), self.q.KeepAll)
        self.assertIsInstance(self.q.grouping(Settings({})), self.q.EachFrameAlone)
        with self.assertRaises(self.config.MissingSetting):
            self.q.grouping(Settings({"grouping": {"enabled": True}}))


if __name__ == "__main__":
    unittest.main()
