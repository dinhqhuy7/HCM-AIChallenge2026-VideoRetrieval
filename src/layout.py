"""Where every artifact lives under the data folder, and how it is written."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable


class DataLayout:
    """One folder per kind of artifact, one file per video.

    data/
      shots/<video>.jsonl       shot ranges (TransNetV2)
      keyframes/<video>.jsonl   the keyframe map: frame index <-> time <-> picture
      frames/<video>/*.jpg      keyframe pictures
      ocr/<video>.jsonl         text read on each indexed keyframe
      asr/<video>.jsonl         speech segments with their times
      objects/<video>.jsonl     objects detected on each indexed keyframe
      index/                    Milvus Lite file and the keyword indexes
      submissions.jsonl         every answer sent to DRES
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def shots(self, video_id: str) -> Path:
        return self.root / "shots" / f"{video_id}.jsonl"

    def keyframes(self, video_id: str) -> Path:
        return self.root / "keyframes" / f"{video_id}.jsonl"

    def frames(self, video_id: str) -> Path:
        return self.root / "frames" / video_id

    def frame_image(self, video_id: str, keyframe_id: str) -> Path:
        return self.frames(video_id) / f"{keyframe_id}.jpg"

    def evidence(self, kind: str, video_id: str) -> Path:
        """``kind`` is ``ocr``, ``asr`` or ``objects``."""
        return self.root / kind / f"{video_id}.jsonl"

    def keyword_index(self, lane: str) -> Path:
        return self.root / "index" / f"keywords-{lane}.json"

    def submissions_log(self) -> Path:
        return self.root / "submissions.jsonl"

    def videos(self) -> list[str]:
        """Videos whose preprocessing finished: the keyframe map is written last."""
        return sorted(path.stem for path in (self.root / "keyframes").glob("*.jsonl"))

    def indexed(self, video_id: str) -> list[dict[str, Any]]:
        """The keyframes of a video that are embedded, read and searched."""
        return [keyframe for keyframe in read_jsonl(self.keyframes(video_id)) if keyframe["indexed"]]

    def evidence_ids(self, kind: str, video_id: str) -> set[str]:
        """Keyframes an ``ocr`` or ``objects`` file covers; empty when there is no file."""
        path = self.evidence(kind, video_id)
        return {record["keyframe_id"] for record in read_jsonl(path)} if path.exists() else set()

    def is_current(self, kind: str, video_id: str) -> bool:
        """Whether an ``ocr`` or ``objects`` file covers exactly the video's indexed keyframes.
        It stops being current when preprocessing changes the keyframes or which are indexed.
        (Speech depends on the video file only, so this does not apply to ``asr``.)"""
        return self.evidence_ids(kind, video_id) == {keyframe["keyframe_id"] for keyframe in self.indexed(video_id)}


def _replace(path: Path, write) -> None:
    """Write to a temporary file next to ``path``, flush it to disk, then swap it in: ``path``
    is the old file or the new one, never half of one. A failed write removes the temporary
    file and leaves ``path`` as it was."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            write(handle)
            handle.flush()
            os.fsync(handle.fileno())  # a full disk shows up here, not as an empty file later
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    def write(handle) -> None:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    _replace(path, write)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: Any) -> None:
    _replace(path, lambda handle: handle.write(json.dumps(value, ensure_ascii=False)))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
