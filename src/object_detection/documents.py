"""Detected objects to one keyword document per shot."""
from __future__ import annotations

from collections import Counter
from typing import Any

from src.layout import DataLayout, read_jsonl
from src.retrieval.keyword_index import Line, ShotDocument


class ObjectDocuments:
    """The labels a shot shows. A label counts as many times as it appears on the keyframe
    where it appears most, so three people in one frame count three, not three per frame,
    and it stands on that keyframe (the earlier one on a tie)."""

    lane = "objects"

    def build(self, layout: DataLayout, video_id: str) -> list[ShotDocument]:
        """The documents of one video, in shot order; a shot with no object has none."""
        keyframes = {keyframe["keyframe_id"]: keyframe for keyframe in layout.indexed(video_id)}
        shots: dict[int, dict[str, tuple[int, dict[str, Any]]]] = {}
        for record in read_jsonl(layout.evidence(self.lane, video_id)):
            keyframe = keyframes.get(record["keyframe_id"])
            if keyframe is None:  # detected before the keyframes changed; the step reports it as not current
                continue
            seen = shots.setdefault(keyframe["shot_id"], {})
            for label, count in Counter(item["label"] for item in record["objects"]).items():
                if label not in seen or count > seen[label][0]:
                    seen[label] = (count, keyframe)
        return [ShotDocument(video_id, shot_id, [Line(label, keyframe["keyframe_id"], keyframe["frame_index"],
                                                      keyframe["time_ms"])
                                                 for label, (count, keyframe) in sorted(seen.items())
                                                 for _ in range(count)])
                for shot_id, seen in sorted(shots.items()) if seen]
