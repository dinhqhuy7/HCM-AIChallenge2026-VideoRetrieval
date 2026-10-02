"""Objects on keyframes with YOLOE and text prompts (Ultralytics, AGPL-3.0).

Runs in its own environment (requirements-objects.txt), so the AGPL dependency never
enters the main one. Usage follows the Ultralytics YOLOE docs: load, set_classes, predict.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.config import Settings

# predict() arguments taken from the ``objects`` section of configs/index.yaml; a key left
# null is not passed, so Ultralytics uses its own value.
OPTIONS = ("conf", "iou", "imgsz")


def prompts(settings: Settings) -> list[str]:
    """The names of the objects to look for: YOLOE finds only what it is told to."""
    classes = list(settings.get("classes") or [])
    if not classes:
        raise ValueError(f"{settings.source}: classes is empty; list the names of the objects to find")
    return classes


def predict_options(settings: Settings, device: str | None = None) -> dict[str, Any]:
    """The options the section sets, and the device (``device`` overrides the section's)."""
    options = {key: settings.get(key) for key in OPTIONS if settings.get(key) is not None}
    device = device or settings.get("device")
    if device:
        options["device"] = device
    return options


class ObjectDetector:
    def __init__(self, settings: Settings, device: str | None = None) -> None:
        """``settings``: the ``objects`` section of configs/index.yaml."""
        from ultralytics import YOLOE

        classes = prompts(settings)
        self.options = predict_options(settings, device)
        self.model = YOLOE(settings.require("weights"))
        self.model.set_classes(classes)

    def detect(self, pictures: list[Path]) -> Iterator[list[dict[str, Any]]]:
        """For each picture, in order, what it shows: label, score, and the box as fractions
        of the picture's size."""
        # One picture per call: given a list, Ultralytics opens every picture and runs them all
        # as one batch, which the keyframes of a whole video do not fit in.
        for picture in pictures:
            (result,) = self.model.predict(str(picture), verbose=False, **self.options)
            yield objects(result)


def objects(result: Any) -> list[dict[str, Any]]:
    boxes = result.boxes
    return [{"label": result.names[int(label)], "score": round(float(score), 4),
             "box": [round(float(value), 4) for value in box]}
            for label, score, box in zip(boxes.cls.tolist(), boxes.conf.tolist(), boxes.xyxyn.tolist())]
