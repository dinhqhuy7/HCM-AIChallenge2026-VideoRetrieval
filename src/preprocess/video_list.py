"""data/videos.csv: the videos this system was built on, and the frame count of the organisers' copies."""
from __future__ import annotations

import csv
from pathlib import Path


class VideoList:
    """Answers are frame numbers in the organisers' copies. A copy of a video from elsewhere
    may have another frame count, and then every frame number it produces is shifted."""

    def __init__(self, path: Path) -> None:
        self.rows: dict[str, dict[str, str]] = {}
        if path.exists():
            with path.open(encoding="utf-8", newline="") as handle:
                self.rows = {row["video_id"]: row for row in csv.DictReader(handle)}

    def mismatch(self, video_id: str, frames: int) -> str | None:
        """A warning when this copy's frame count differs from the listed one; None when it
        matches, or when the video is not in the list."""
        row = self.rows.get(video_id)
        if row is None or int(row["frames"]) == frames:
            return None
        return (f"{video_id}: this copy has {frames} frames, the organisers' copy has {row['frames']} "
                f"({row['fps']} fps); its frame numbers will not match their answers")
