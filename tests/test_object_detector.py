"""ObjectDetector with a stand-in model, and YOLOE itself when YOLOE_WEIGHTS is set (run it in the
objects environment):

    YOLOE_WEIGHTS=yoloe-26l-seg.pt python -m unittest tests.test_object_detector
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_YAML = importlib.util.find_spec("yaml") is not None


class Values(list):
    def tolist(self):
        return list(self)


def result(names, found):
    """A result shaped like Ultralytics': class numbers, scores and boxes as fractions."""
    return SimpleNamespace(names=names, boxes=SimpleNamespace(cls=Values(c for c, _, _ in found),
                                                              conf=Values(s for _, s, _ in found),
                                                              xyxyn=Values(b for _, _, b in found)))


class FakeModel:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def predict(self, source, **options):
        if not isinstance(source, str):
            raise AssertionError("a list is run as one batch; the detector must pass one picture per call")
        self.calls.append((source, options))
        return [next(self.results)]


@unittest.skipUnless(HAVE_YAML, "needs PyYAML")
class ObjectDetectorTest(unittest.TestCase):
    def settings(self, values):
        from src.config import Settings

        return Settings(values, "index.yaml:objects")

    def detector(self, results, options=None):
        from src.object_detection.detector import ObjectDetector

        detector = ObjectDetector.__new__(ObjectDetector)  # no model: the stand-in answers
        detector.model, detector.options = FakeModel(results), options or {}
        return detector

    def test_no_prompt_is_an_error_that_names_the_key(self):
        from src.object_detection.detector import prompts

        for classes in ([], None):
            with self.assertRaisesRegex(ValueError, "index.yaml:objects: classes is empty"):
                prompts(self.settings({"classes": classes}))
        self.assertEqual(prompts(self.settings({"classes": ["person", "car"]})), ["person", "car"])

    def test_only_the_options_that_are_set_reach_predict(self):
        from src.object_detection.detector import predict_options

        settings = self.settings({"conf": None, "iou": 0.7, "imgsz": None, "device": "cpu", "weights": "x.pt"})
        self.assertEqual(predict_options(settings), {"iou": 0.7, "device": "cpu"})
        self.assertEqual(predict_options(settings, "cuda:1"), {"iou": 0.7, "device": "cuda:1"})
        self.assertEqual(predict_options(self.settings({})), {})

    def test_labels_scores_and_boxes_for_each_picture_in_order(self):
        detector = self.detector([result({0: "person", 1: "car"}, [(1.0, 0.876543, [0.1, 0.2, 0.30004, 0.4]),
                                                                   (0.0, 0.5, [0.5, 0.5, 1.0, 1.0])]),
                                  result({0: "person", 1: "car"}, [])], {"conf": 0.3})
        self.assertEqual(list(detector.detect([Path("a.jpg"), Path("b.jpg")])), [
            [{"label": "car", "score": 0.8765, "box": [0.1, 0.2, 0.3, 0.4]},
             {"label": "person", "score": 0.5, "box": [0.5, 0.5, 1.0, 1.0]}],
            [],
        ])
        self.assertEqual(detector.model.calls, [("a.jpg", {"verbose": False, "conf": 0.3}),
                                                ("b.jpg", {"verbose": False, "conf": 0.3})])

    def test_pictures_are_read_one_at_a_time(self):
        detector = self.detector([result({0: "person"}, [])] * 1000)
        next(detector.detect([Path("a.jpg")] * 1000))
        self.assertEqual(len(detector.model.calls), 1)


@unittest.skipUnless(importlib.util.find_spec("ultralytics") and os.environ.get("YOLOE_WEIGHTS"),
                     "set YOLOE_WEIGHTS to run YOLOE")
class YoloeTest(unittest.TestCase):
    def test_a_blank_picture_shows_nothing(self):
        from PIL import Image

        from src.config import Settings
        from src.object_detection.detector import ObjectDetector

        settings = Settings({"weights": os.environ["YOLOE_WEIGHTS"], "classes": ["person", "car"]})
        detector = ObjectDetector(settings, os.environ.get("TEST_DEVICE", "cpu"))
        with tempfile.TemporaryDirectory() as folder:
            picture = Path(folder) / "blank.jpg"
            Image.new("RGB", (640, 360), "gray").save(picture)
            self.assertEqual(list(detector.detect([picture])), [[]])


if __name__ == "__main__":
    unittest.main()
