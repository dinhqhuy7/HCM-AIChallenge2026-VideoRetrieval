"""Which frames of a shot become keyframes."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.config import Settings


@dataclass(frozen=True)
class Slot:
    """One keyframe to pick: the frames it may be picked from, in order."""

    shot_id: int
    candidates: range


class KeyframePolicy(ABC):
    @abstractmethod
    def slots(self, shot_id: int, start: int, end: int) -> list[Slot]:
        """Slots for the shot [start, end], ends inclusive, in time order."""


class MiddleFrame(KeyframePolicy):
    """One keyframe, the middle frame of the shot."""

    def slots(self, shot_id: int, start: int, end: int) -> list[Slot]:
        middle = (start + end) // 2
        return [Slot(shot_id, range(middle, middle + 1))]


class DenseFrames(KeyframePolicy):
    """A slot every ``frame_gap`` frames, centred in the shot; each takes the sharpest frame
    within ``search_radius`` frames of its position. A shot shorter than the gap gets one slot.

    Inside a shot, neighbouring keyframes are at most ``frame_gap + 2 * search_radius``
    frames apart; across a cut, at most ``2 * frame_gap - 1 + 2 * search_radius``, because
    the slots are centred in each shot.
    """

    def __init__(self, frame_gap: int, search_radius: int) -> None:
        if frame_gap < 1 or search_radius < 0 or 2 * search_radius >= frame_gap:
            raise ValueError("dense keyframes need frame_gap >= 1 and 2 * search_radius < frame_gap, "
                             "so that two slots never share a frame")
        self.frame_gap = frame_gap
        self.search_radius = search_radius

    def slots(self, shot_id: int, start: int, end: int) -> list[Slot]:
        length = end - start + 1
        count = max(1, length // self.frame_gap)
        first = start + (length - (count - 1) * self.frame_gap) // 2
        return [Slot(shot_id, range(max(start, target - self.search_radius), min(end, target + self.search_radius) + 1))
                for target in (first + n * self.frame_gap for n in range(count))]


def keyframe_policy(settings: Settings) -> KeyframePolicy:
    """``keyframes.policy`` in configs/preprocess.yaml: ``middle`` or ``dense``."""
    policies = {
        "middle": lambda: MiddleFrame(),
        "dense": lambda: DenseFrames(
            int(settings.require("keyframes.dense.frame_gap",
                                 "no published default; see docs/offline/01-shots-and-keyframes.md")),
            int(settings.require("keyframes.dense.search_radius", "0 keeps the frame at the slot itself"))),
    }
    policy = settings.get("keyframes.policy", "middle")
    if policy not in policies:
        raise ValueError(f"{settings.source}: keyframes.policy must be one of {sorted(policies)}")
    return policies[policy]()
