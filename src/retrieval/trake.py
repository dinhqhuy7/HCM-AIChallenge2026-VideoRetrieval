"""TRAKE: one video, one keyframe per event, the events in order.

The task comes in two stages, and so does this module:

1. retrieval  every event searches the whole collection; a video scores the sum, over the
              events, of its best frame for that event
2. alignment  inside each candidate video, every keyframe is scored against every event and
              the best chain in time order is found by dynamic programming

A chain is scored as a whole. Taking the best frame of each event on its own can put a later
event before an earlier one with almost the same total; only the order constraint tells those
two apart. Every keyframe of a candidate video is scored, so every chain has all n events,
and chains compare by their total.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from src.retrieval.hits import Frame
from src.retrieval.lanes import VisualLane


@dataclass(frozen=True)
class Chain:
    video_id: str
    frames: tuple[Frame, ...]
    score: float


@dataclass(frozen=True)
class ChainRules:
    """strict: each event after the one before it; loose: at the same time or later.
    The gaps are milliseconds between consecutive events; None leaves that side open."""

    order: str = "strict"
    min_gap_ms: int | None = None
    max_gap_ms: int | None = None

    def __post_init__(self) -> None:
        if self.order not in ("strict", "loose"):
            raise ValueError("order must be 'strict' or 'loose'")
        if self.min_gap_ms is not None and self.max_gap_ms is not None and self.min_gap_ms > self.max_gap_ms:
            raise ValueError("min_gap_ms must not be larger than max_gap_ms")

    def windows(self, times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """For each frame, the positions [start, end) of the frames allowed to follow it."""
        # Without a minimum gap, "strict" still has to move past frames shown at the same time.
        side = "right" if self.order == "strict" and not self.min_gap_ms else "left"
        starts = np.searchsorted(times, times + (self.min_gap_ms or 0), side=side)
        if self.max_gap_ms is None:
            return starts, np.full(len(times), len(times))
        return starts, np.searchsorted(times, times + self.max_gap_ms, side="right")


class ChainAligner:
    """The best chain starting at each keyframe of one video."""

    def __init__(self, rules: ChainRules) -> None:
        self.rules = rules

    def chains(self, frames: list[Frame], scores: np.ndarray) -> list[Chain]:
        """``frames`` in time order; ``scores[event, position]`` is how well a frame fits an event."""
        events, count = scores.shape
        if count != len(frames):
            raise ValueError(f"{count} columns of scores for {len(frames)} frames")
        starts, ends = self.rules.windows(np.asarray([frame.time_ms for frame in frames], dtype=np.int64))
        best = scores[-1].astype(np.float64)  # the last event ends a chain wherever it stands
        follow = np.full((events, count), -1, dtype=np.int64)
        for event in range(events - 2, -1, -1):
            total = np.full(count, -np.inf)
            for position in range(count):
                start, end = starts[position], ends[position]
                if start >= end:
                    continue  # nothing may follow this frame, so no chain starts here
                step = start + int(np.argmax(best[start:end]))
                if np.isfinite(best[step]):
                    total[position] = scores[event, position] + best[step]
                    follow[event, position] = step
            best = total
        chains = []
        for position in np.flatnonzero(np.isfinite(best)):
            path = [int(position)]
            for event in range(events - 1):
                path.append(int(follow[event, path[-1]]))
            chosen = tuple(replace(frames[p], score=float(scores[e, p])) for e, p in enumerate(path))
            chains.append(Chain(frames[0].video_id, chosen, float(best[position])))
        chains.sort(key=lambda chain: (-chain.score, chain.frames[0].frame_index))
        return chains


class TrakeSearch:
    def __init__(self, lane: VisualLane, rules: ChainRules, depth: int, rows: int, spread: bool) -> None:
        self.lane = lane
        self.aligner = ChainAligner(rules)
        self.depth = depth
        self.rows = rows
        self.spread = spread

    def search(self, events: list[str]) -> list[Chain]:
        if len(events) < 2:
            raise ValueError("TRAKE needs at least two events")
        vectors = np.stack([self.lane.embed(event) for event in events])
        per_video: dict[str, list[Chain]] = {}
        for video_id in self.videos(vectors):
            frames, matrix = self.lane.index.frames_of(video_id)
            chains = self.aligner.chains(frames, vectors @ matrix.T) if frames else []
            if chains:
                per_video[video_id] = chains[:self.rows]
        return self.order(per_video)[:self.rows]

    def videos(self, vectors: np.ndarray) -> list[str]:
        """Stage 1: videos ranked by the sum over the events of their best frame."""
        totals: dict[str, float] = {}
        for vector in vectors:
            best: dict[str, float] = {}
            for frame in self.lane.index.search(vector, self.depth):
                best[frame.video_id] = max(best.get(frame.video_id, -np.inf), frame.score)
            for video_id, score in best.items():
                totals[video_id] = totals.get(video_id, 0.0) + score
        return sorted(totals, key=lambda video: (-totals[video], video))[:self.rows]

    def order(self, per_video: dict[str, list[Chain]]) -> list[Chain]:
        """By score; or, with spread, the best chain of every video first, then every second best ...

        A wrong video scores zero however well its frames line up, so spreading the rows over
        videos is what keeps the tail of the list worth anything.
        """
        if not self.spread:
            every = [chain for chains in per_video.values() for chain in chains]
            return sorted(every, key=lambda chain: (-chain.score, chain.video_id, chain.frames[0].frame_index))
        videos = sorted(per_video, key=lambda video: (-per_video[video][0].score, video))
        longest = max((len(chains) for chains in per_video.values()), default=0)
        return [per_video[video][turn] for turn in range(longest) for video in videos if turn < len(per_video[video])]
