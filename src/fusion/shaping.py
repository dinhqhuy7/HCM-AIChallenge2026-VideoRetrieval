"""From a ranking of shots to the rows that get scored.

The organisers' information document for the round scores a query as the mean of R@1, R@5,
R@20, R@50 and R@100, so the order of the rows is the score, and every empty row is a chance
given away.
"""
from __future__ import annotations

from collections import OrderedDict, deque

from src.retrieval.hits import Frame, ShotHit


class VideoSpread:
    """Keep the first ``keep_top`` rows as ranked, then take ``per_video`` rows from each video
    in turn.

    A tail that sits in two videos is lost entirely when both videos are wrong. There are no
    published values for the two numbers, so configs/search.yaml leaves this off.
    """

    def __init__(self, keep_top: int, per_video: int) -> None:
        if keep_top < 0 or per_video < 1:
            raise ValueError("spread needs keep_top >= 0 and per_video >= 1")
        self.keep_top = keep_top
        self.per_video = per_video

    def apply(self, frames: list[Frame]) -> list[Frame]:
        """The same frames, reordered: no row is added, dropped or repeated."""
        spread, queues = frames[:self.keep_top], OrderedDict()
        for frame in frames[self.keep_top:]:
            queues.setdefault(frame.video_id, deque()).append(frame)
        while queues:
            for video in list(queues):  # the videos keep the order in which they were first seen
                queue = queues[video]
                for _ in range(min(self.per_video, len(queue))):
                    spread.append(queue.popleft())
                if not queue:
                    del queues[video]
        return spread


class ResultShaper:
    """One row per shot, then the spare frames of those shots, cut at ``rows``."""

    def __init__(self, rows: int, spread: VideoSpread | None = None) -> None:
        if rows < 1:
            raise ValueError("rows must be 1 or more")
        self.rows = rows
        self.spread = spread

    def shape(self, shots: list[ShotHit]) -> list[Frame]:
        frames = [shot.frame for shot in shots]
        if self.spread is not None:
            frames = self.spread.apply(frames)
        # A second frame of a shot is worth less than a new shot, but more than an empty row:
        # it can still fall inside the answer range when the shot straddles its edge.
        spare = [frame for shot in shots for frame in shot.others]
        return (frames + spare)[:self.rows]
