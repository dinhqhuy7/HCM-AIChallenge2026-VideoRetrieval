"""Decoding a video with PyAV, frame by frame, with each frame's own timestamp."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class DecodedFrame:
    index: int            # position in the order frames come out of the decoder; the first is 0
    pts: int | None       # presentation timestamp, in time_base units
    time_base: Fraction
    time_ms: int
    time_source: str      # "pts", or "index" when the stream carried no timestamp
    frame: Any            # av.VideoFrame; .to_image() gives a PIL picture


class VideoReader:
    """Time comes from each frame's PTS, not from index / fps: the two disagree on
    variable-frame-rate video, and the time is what gets submitted for KIS and Q&A."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> "VideoReader":
        import av

        self.container = av.open(str(self.path))
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"  # PyAV cookbook: decode on several threads
        self.fps = Fraction(self.stream.average_rate or self.stream.guessed_rate or 0)
        return self

    def __exit__(self, *exc: object) -> None:
        self.container.close()

    def frames(self) -> Iterator[DecodedFrame]:
        for index, frame in enumerate(self.container.decode(self.stream)):
            time_base = Fraction(frame.time_base or self.stream.time_base)
            if frame.pts is not None:
                yield DecodedFrame(index, frame.pts, time_base, round(frame.pts * time_base * 1000), "pts", frame)
            else:
                yield DecodedFrame(index, None, time_base, round(Fraction(index) / self.fps * 1000), "index", frame)
