"""OCR lines to one keyword document per shot."""
from __future__ import annotations

from src.layout import DataLayout, read_jsonl
from src.retrieval.keyword_index import Line, ShotDocument
from src.retrieval.text import tidy, tokens


class OcrDocuments:
    """Every distinct line a shot shows, once, in its best-scoring reading.

    OCR runs on every indexed keyframe, and a caption held for two seconds is read on each
    keyframe of the shot. Collapsing repeated readings keeps a shot from voting fifty times
    for one headline, while different lines -- a logo, a clock, a headline -- stay separate
    pieces of evidence. Two readings are one line when their folded words are the same, so
    case, Vietnamese marks and spacing do not split them.
    """

    lane = "ocr"

    def build(self, layout: DataLayout, video_id: str) -> list[ShotDocument]:
        """The documents of one video, in shot order; a shot with no words has none."""
        keyframes = {keyframe["keyframe_id"]: keyframe for keyframe in layout.indexed(video_id)}
        shots: dict[int, dict[str, tuple[float, Line]]] = {}
        for reading in read_jsonl(layout.evidence(self.lane, video_id)):
            keyframe = keyframes.get(reading["keyframe_id"])
            if keyframe is None:  # read before the keyframes changed; the step reports it as not current
                continue
            seen = shots.setdefault(keyframe["shot_id"], {})
            for line in reading["lines"]:
                key = " ".join(tokens(line["text"]))
                if key and (key not in seen or line["score"] > seen[key][0]):
                    seen[key] = (line["score"], Line(tidy(line["text"]), keyframe["keyframe_id"],
                                                     keyframe["frame_index"], keyframe["time_ms"]))
        return [ShotDocument(video_id, shot_id, [line for _, line in seen.values()])
                for shot_id, seen in sorted(shots.items()) if seen]
