"""Frame quality, and near-duplicate keyframes.

Both only decide what goes into the index. Pictures and the keyframe map are always kept,
so any answer can still be traced back to its frame.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from PIL import Image

from src.config import Settings


def measure(image: Image.Image) -> dict[str, float]:
    """sharpness: variance of the Laplacian (the usual blur measure, computed with OpenCV);
    brightness: mean grey level, 0-255; entropy: of the grey-level histogram, in bits
    (one colour is 0.0; the ``+ 0.0`` keeps it from printing as -0.0)."""
    import cv2

    grey = np.asarray(image.convert("L"))
    histogram = np.bincount(grey.ravel(), minlength=256) / grey.size
    histogram = histogram[histogram > 0]
    return {"sharpness": round(float(cv2.Laplacian(grey, cv2.CV_64F).var()), 3),
            "brightness": round(float(grey.mean()), 3),
            "entropy": round(float(-(histogram * np.log2(histogram)).sum()), 4) + 0.0}


def dhash(image: Image.Image, size: int = 8) -> str:
    """Difference hash (N. Krawetz, "Kind of Like That", 2013): shrink to (size+1) x size grey
    pixels and keep one bit per pair of horizontal neighbours. size 8 gives 64 bits, as hex."""
    pixels = np.asarray(image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS), dtype=np.int16)
    bits = (pixels[:, 1:] > pixels[:, :-1]).flatten()
    return f"{int(''.join('1' if bit else '0' for bit in bits), 2):0{size * size // 4}x}"


def hamming(first: str, second: str) -> int:
    return bin(int(first, 16) ^ int(second, 16)).count("1")


class QualityGate(ABC):
    @abstractmethod
    def reason(self, metrics: dict[str, float]) -> str | None:
        """Why a frame stays out of the index, or None to keep it."""


class KeepAll(QualityGate):
    def reason(self, metrics: dict[str, float]) -> str | None:
        return None


class Thresholds(QualityGate):
    """Frames below a floor or above a ceiling stay out of the index. A threshold left
    empty is not checked. Look at what dark and bright remove before keeping them: a night
    scene is still evidence."""

    CHECKS = (("blur", "sharpness", "min_sharpness", -1), ("dark", "brightness", "min_brightness", -1),
              ("bright", "brightness", "max_brightness", 1), ("flat", "entropy", "min_entropy", -1))

    def __init__(self, settings: Settings) -> None:
        self.limits = [(reason, metric, float(settings.get(key)), side)
                       for reason, metric, key, side in self.CHECKS if settings.get(key) is not None]
        if not self.limits:
            raise ValueError(f"{settings.source}: quality is enabled but no threshold is set")

    def reason(self, metrics: dict[str, float]) -> str | None:
        for reason, metric, limit, side in self.limits:
            if (metrics[metric] - limit) * side > 0:
                return reason
        return None


class Grouping(ABC):
    @abstractmethod
    def assign(self, keyframes: list[dict[str, Any]], first_group: int) -> int:
        """Set ``group`` and ``indexed`` on the keyframes of one shot, in time order.
        Returns the next free group number."""


class EachFrameAlone(Grouping):
    """No grouping: every kept keyframe is its own group; rejected frames sit in none."""

    def assign(self, keyframes: list[dict[str, Any]], first_group: int) -> int:
        kept = [keyframe for keyframe in keyframes if keyframe["rejected"] is None]
        for keyframe in keyframes:
            keyframe["group"], keyframe["indexed"] = None, False
        for number, keyframe in enumerate(kept, start=first_group):
            keyframe["group"], keyframe["indexed"] = number, True
        return first_group + len(kept)


class NearDuplicates(Grouping):
    """Consecutive kept keyframes whose dHash differ in at most ``max_distance`` bits form one
    group; only its sharpest frame is indexed. Rejected frames sit in no group."""

    def __init__(self, max_distance: int) -> None:
        self.max_distance = max_distance

    def assign(self, keyframes: list[dict[str, Any]], first_group: int) -> int:
        groups: list[list[dict[str, Any]]] = []
        previous = None
        for keyframe in keyframes:
            keyframe["group"], keyframe["indexed"] = None, False
            if keyframe["rejected"] is not None:
                continue
            if previous is not None and hamming(previous["dhash"], keyframe["dhash"]) <= self.max_distance:
                groups[-1].append(keyframe)
            else:
                groups.append([keyframe])
            previous = keyframe
        for number, members in enumerate(groups, start=first_group):
            for keyframe in members:
                keyframe["group"] = number
            max(members, key=lambda keyframe: keyframe["sharpness"])["indexed"] = True
        return first_group + len(groups)


def quality_gate(settings: Settings) -> QualityGate:
    """``quality`` in configs/preprocess.yaml."""
    return Thresholds(settings.section("quality")) if settings.get("quality.enabled") else KeepAll()


def grouping(settings: Settings) -> Grouping:
    """``grouping`` in configs/preprocess.yaml."""
    if not settings.get("grouping.enabled"):
        return EachFrameAlone()
    return NearDuplicates(int(settings.require("grouping.max_distance", "no published default; "
                                               "see docs/offline/01-shots-and-keyframes.md")))
