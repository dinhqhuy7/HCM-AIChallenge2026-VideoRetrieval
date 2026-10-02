"""OcrReader with a stand-in pipeline, and the real PaddleOCR models when OCR_MODELS is set
(run it in the OCR environment):

    OCR_MODELS=PP-OCRv6_medium_det,PP-OCRv6_medium_rec python -m unittest tests.test_ocr_reader
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("numpy", "yaml"))


def page(width, height, texts, scores, boxes):
    """A result shaped like PaddleOCR's: the boxes are x0, y0, x1, y1 in pixels."""
    import numpy as np

    return {"doc_preprocessor_res": {"output_img": np.zeros((height, width, 3), dtype=np.uint8)},
            "rec_texts": texts, "rec_scores": scores, "rec_boxes": np.array(boxes, dtype=np.int16)}


class FakePipeline:
    def __init__(self, pages):
        self.pages = pages
        self.produced = 0

    def predict(self, inputs):
        raise AssertionError("predict keeps every result; the reader must use predict_iter")

    def predict_iter(self, inputs):
        for name in inputs:
            self.produced += 1
            yield self.pages[Path(name).name]


@unittest.skipUnless(HAVE_LIBRARIES, "needs numpy and PyYAML")
class OcrReaderTest(unittest.TestCase):
    def options(self, values, device=None):
        from src.config import Settings
        from src.ocr.reader import paddleocr_options

        return paddleocr_options(Settings(values, "index.yaml:ocr"), device)

    def reader(self, pages):
        from src.ocr.reader import OcrReader

        reader = OcrReader.__new__(OcrReader)  # no PaddleOCR: the stand-in answers
        reader.pipeline = FakePipeline(pages)
        return reader

    def test_only_the_options_that_are_set_reach_paddleocr(self):
        options = self.options({"text_recognition_model_name": "PP-OCRv6_medium_rec", "text_det_thresh": None,
                                "use_doc_unwarping": False, "device": "cuda:1", "not_an_option": 1})
        self.assertEqual(options, {"text_recognition_model_name": "PP-OCRv6_medium_rec", "use_doc_unwarping": False,
                                   "device": "gpu:1"})

    def test_the_device_argument_wins_and_none_leaves_it_to_paddle(self):
        self.assertEqual(self.options({"device": "cpu"}, "cuda:0"), {"device": "gpu:0"})
        self.assertEqual(self.options({"device": None}), {})

    def test_paddle_device_names(self):
        from src.ocr.reader import paddle_device

        self.assertEqual([paddle_device(name) for name in ("cuda", "cuda:3", "gpu:2", "cpu")],
                         ["gpu", "gpu:3", "gpu:2", "cpu"])

    def test_lines_as_fractions_of_each_picture(self):
        reader = self.reader({
            "wide.jpg": page(1280, 720, ["HTV9", "  ", "Tin chính"], [0.987654, 0.5, 0.9],
                             [[1152, 36, 1280, 72], [0, 0, 10, 10], [0, 648, 640, 720]]),
            "tall.jpg": page(720, 1280, ["10"], [0.99], [[120, 1216, 152, 1260]]),
            "blank.jpg": page(1280, 720, [], [], []),
        })
        self.assertEqual(list(reader.read([Path("wide.jpg"), Path("tall.jpg"), Path("blank.jpg")])), [
            [{"text": "HTV9", "score": 0.9877, "box": [0.9, 0.05, 1.0, 0.1]},
             {"text": "Tin chính", "score": 0.9, "box": [0.0, 0.9, 0.5, 1.0]}],
            [{"text": "10", "score": 0.99, "box": [0.1667, 0.95, 0.2111, 0.9844]}],
            [],
        ])

    def test_pictures_are_read_one_at_a_time(self):
        reader = self.reader({"wide.jpg": page(1280, 720, [], [], [])})
        next(reader.read([Path("wide.jpg")] * 1000))
        self.assertEqual(reader.pipeline.produced, 1)


@unittest.skipUnless(importlib.util.find_spec("paddleocr") and os.environ.get("OCR_MODELS"),
                     "set OCR_MODELS to run the real models")
class OcrModelTest(unittest.TestCase):
    def test_reads_printed_words_near_the_bottom_of_a_portrait_picture(self):
        from PIL import Image, ImageDraw, ImageFont

        from src.config import Settings
        from src.ocr.reader import OcrReader

        detection, recognition = os.environ["OCR_MODELS"].split(",")
        settings = Settings({"text_detection_model_name": detection, "text_recognition_model_name": recognition,
                             "use_doc_orientation_classify": False, "use_doc_unwarping": False,
                             "use_textline_orientation": False})
        reader = OcrReader(settings, os.environ.get("TEST_DEVICE", "cpu"))
        with tempfile.TemporaryDirectory() as folder:
            picture = Path(folder) / "words.png"
            image = Image.new("RGB", (720, 1280), "white")
            ImageDraw.Draw(image).text((60, 1100), "HELLO 2026", fill="black", font=ImageFont.load_default(size=72))
            image.save(picture)
            [found] = list(reader.read([picture]))
        self.assertIn("HELLO 2026", " ".join(line["text"] for line in found))
        x0, y0, x1, y1 = found[0]["box"]
        self.assertTrue(0.0 <= x0 < x1 <= 1.0 and 0.8 < y0 < y1 <= 1.0, found[0]["box"])


if __name__ == "__main__":
    unittest.main()
