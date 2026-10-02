"""Reading text on keyframes with the PaddleOCR 3.x general OCR pipeline."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.config import Settings

# PaddleOCR() arguments taken from the ``ocr`` section of configs/index.yaml. A key left null
# is not passed, so PaddleOCR uses its own value (the pipeline's OCR.yaml in PaddleX).
OPTIONS = ("text_detection_model_name", "text_recognition_model_name", "use_doc_orientation_classify",
           "use_doc_unwarping", "use_textline_orientation", "text_det_limit_side_len", "text_det_limit_type",
           "text_det_thresh", "text_det_box_thresh", "text_det_unclip_ratio", "text_rec_score_thresh")


def paddle_device(device: str) -> str:
    """Paddle names GPUs gpu:N and rejects cuda:N, which the other steps use."""
    return str(device).replace("cuda", "gpu", 1) if str(device).startswith("cuda") else str(device)


def paddleocr_options(settings: Settings, device: str | None = None) -> dict[str, Any]:
    """The options the ``ocr`` section sets, and the device (``device`` overrides the section's).
    With no device at all, Paddle takes gpu:0 when it sees a GPU."""
    options = {key: settings.get(key) for key in OPTIONS if settings.get(key) is not None}
    device = device or settings.get("device")
    if device:
        options["device"] = paddle_device(device)
    return options


class OcrReader:
    def __init__(self, settings: Settings, device: str | None = None) -> None:
        """``settings``: the ``ocr`` section of configs/index.yaml."""
        from paddleocr import PaddleOCR

        self.pipeline = PaddleOCR(**paddleocr_options(settings, device))

    def read(self, pictures: list[Path]) -> Iterator[list[dict[str, Any]]]:
        """For each picture, in order, its lines: text, recognition score, and the box as
        fractions of the picture's size (videos are not all the same shape: some are portrait)."""
        # predict_iter, not predict: predict keeps every result, and each result holds its picture.
        for page in self.pipeline.predict_iter([str(picture) for picture in pictures]):
            yield lines(page)


def lines(page: Any) -> list[dict[str, Any]]:
    height, width = page["doc_preprocessor_res"]["output_img"].shape[:2]  # the picture the boxes are on
    found = []
    for text, score, box in zip(page["rec_texts"], page["rec_scores"], page["rec_boxes"]):
        if text.strip():
            x0, y0, x1, y1 = (float(value) for value in box)
            found.append({"text": text, "score": round(float(score), 4),
                          "box": [round(x0 / width, 4), round(y0 / height, 4), round(x1 / width, 4),
                                  round(y1 / height, 4)]})
    return found
