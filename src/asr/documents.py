"""Speech segments to one keyword document per shot."""
from __future__ import annotations

from typing import Any

from src.layout import DataLayout, read_jsonl
from src.retrieval.keyword_index import Line, ShotDocument


class SpeechDocuments:
    """A segment is attached, whole, to every shot its time span touches.

    Speech does not stop at shot boundaries. Cutting it there splits a phrase in two ("Châu
    Âu" into "Châu" and "Âu") and a search for the phrase finds neither half. ``padding_ms``
    widens each segment on both sides, for a voice that runs ahead of or behind the picture;
    0 keeps the times Whisper gave. In each shot, the line stands on the indexed keyframe
    nearest to when the segment is heard there.
    """

    lane = "asr"

    def __init__(self, padding_ms: int) -> None:
        self.padding_ms = padding_ms

    def build(self, layout: DataLayout, video_id: str) -> list[ShotDocument]:
        shots = read_jsonl(layout.shots(video_id))  # each spans [start_ms, end_ms)
        keyframes: dict[int, list[dict[str, Any]]] = {}
        for keyframe in layout.indexed(video_id):
            keyframes.setdefault(keyframe["shot_id"], []).append(keyframe)
        lines: dict[int, list[Line]] = {}
        for segment in read_jsonl(layout.evidence(self.lane, video_id)):
            start, end = segment["start_ms"] - self.padding_ms, segment["end_ms"] + self.padding_ms
            for shot in shots:
                if shot["start_ms"] < end and shot["end_ms"] > start and shot["shot_id"] in keyframes:
                    heard = min(max(segment["start_ms"], shot["start_ms"]), shot["end_ms"])
                    nearest = min(keyframes[shot["shot_id"]], key=lambda keyframe: abs(keyframe["time_ms"] - heard))
                    lines.setdefault(shot["shot_id"], []).append(
                        Line(segment["text"], nearest["keyframe_id"], nearest["frame_index"], nearest["time_ms"]))
        return [ShotDocument(video_id, shot_id, shot_lines) for shot_id, shot_lines in sorted(lines.items())]
