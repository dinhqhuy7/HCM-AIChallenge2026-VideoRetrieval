"""What a search returns: frames, and shots that group them."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Frame:
    """One keyframe that a lane found, with the lane's score for it."""

    video_id: str
    shot_id: int
    keyframe_id: str
    frame_index: int
    time_ms: int
    score: float = 0.0

    @property
    def shot(self) -> tuple[str, int]:
        return self.video_id, self.shot_id


@dataclass
class ShotHit:
    """A shot in a ranking: the frame that stands for it, and the other frames found in it.

    Shots, not frames, are what gets ranked and fused. Fifty frames of one headline are one
    piece of evidence; ranked as frames, they would outvote fifty different shots.
    """

    frame: Frame
    score: float
    others: list[Frame] = field(default_factory=list)

    @property
    def shot(self) -> tuple[str, int]:
        return self.frame.shot


def group_by_shot(frames: list[Frame]) -> list[ShotHit]:
    """Collapse a ranked list of frames into shots. Each shot stands at the rank of its first
    (best) frame and keeps that frame's score; the shot's later frames go into ``others``."""
    shots: dict[tuple[str, int], ShotHit] = {}
    for frame in frames:
        hit = shots.get(frame.shot)
        if hit is None:
            shots[frame.shot] = ShotHit(frame, frame.score)
        else:
            hit.others.append(frame)
    return list(shots.values())
