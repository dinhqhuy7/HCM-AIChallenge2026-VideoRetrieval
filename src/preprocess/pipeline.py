"""Offline step 1 for one video: shots, keyframes, pictures and the keyframe map."""
from __future__ import annotations

import shutil
from itertools import groupby
from pathlib import Path
from typing import Any

from src.layout import DataLayout, read_jsonl, write_jsonl
from src.preprocess.keyframes import KeyframePolicy, Slot
from src.preprocess.quality import Grouping, QualityGate, dhash, measure
from src.preprocess.shots import ShotDetector
from src.preprocess.video import DecodedFrame, VideoReader

MEASUREMENTS = ("sharpness", "brightness", "entropy")


class FrameCountMismatch(RuntimeError):
    """TransNetV2 and PyAV saw a different number of frames, so shot boundaries and frame
    indexes would not refer to the same frames."""


class Preprocessor:
    def __init__(self, layout: DataLayout, detector: ShotDetector | None, policy: KeyframePolicy | None,
                 gate: QualityGate, grouping: Grouping, jpeg_quality: int) -> None:
        self.layout = layout
        self.detector = detector
        self.policy = policy
        self.gate = gate
        self.grouping = grouping
        self.jpeg_quality = jpeg_quality

    def run(self, video: Path, video_id: str) -> dict[str, int]:
        """Everything is built aside and swapped in at the end: if this fails, the video's
        previous pictures and keyframe map are left exactly as they were."""
        partial = self.layout.frames(video_id).with_name(f"{video_id}.partial")
        shutil.rmtree(partial, ignore_errors=True)
        try:
            return self._build(video, video_id, partial)
        except BaseException:
            shutil.rmtree(partial, ignore_errors=True)
            raise

    def _build(self, video: Path, video_id: str, partial: Path) -> dict[str, int]:
        shots, model_frames = self.detector.detect(video)
        slots = [slot for shot_id, (start, end) in enumerate(shots) for slot in self.policy.slots(shot_id, start, end)]
        owner = {index: number for number, slot in enumerate(slots) for index in slot.candidates}
        starts = {start: shot_id for shot_id, (start, _) in enumerate(shots)}

        keyframes: list[dict[str, Any]] = []
        best: dict[int, tuple[DecodedFrame, Any, dict[str, float]]] = {}
        start_ms: dict[int, int] = {}
        first = last = None
        with VideoReader(video) as reader:
            for decoded in reader.frames():
                first, last = first or decoded, decoded
                if decoded.index in starts:
                    start_ms[starts[decoded.index]] = decoded.time_ms
                number = owner.get(decoded.index)
                if number is None:
                    continue
                image = decoded.frame.to_image()
                metrics = measure(image)
                if number not in best or metrics["sharpness"] > best[number][2]["sharpness"]:
                    best[number] = (decoded, image, metrics)
                if decoded.index == slots[number].candidates[-1]:
                    keyframes.append(self._keep(video_id, partial, slots[number], *best.pop(number)))
            frame_ms = 1000 / reader.fps if reader.fps else 0

        decoded_frames = last.index + 1 if last else 0
        if decoded_frames != model_frames or not decoded_frames:
            raise FrameCountMismatch(f"{video_id}: PyAV decoded {decoded_frames} frames, TransNetV2 saw {model_frames}")

        end_ms = [start_ms[shot_id + 1] for shot_id in range(len(shots) - 1)] + [round(last.time_ms + frame_ms)]
        shot_records = [{"video_id": video_id, "shot_id": shot_id, "start_frame": start, "end_frame": end,
                         "start_ms": start_ms[shot_id], "end_ms": end_ms[shot_id]}
                        for shot_id, (start, end) in enumerate(shots)]
        self._select(keyframes)
        final = self.layout.frames(video_id)
        shutil.rmtree(final, ignore_errors=True)
        partial.mkdir(parents=True, exist_ok=True)
        partial.rename(final)
        write_jsonl(self.layout.shots(video_id), shot_records)
        write_jsonl(self.layout.keyframes(video_id), keyframes)  # written last: marks the video done
        return {"frames": decoded_frames, "shots": len(shots), "keyframes": len(keyframes),
                "indexed": sum(keyframe["indexed"] for keyframe in keyframes), "first_frame_ms": first.time_ms}

    def reselect(self, video_id: str) -> dict[str, int]:
        """Apply the current quality and grouping settings again, from the measurements already
        in the keyframe map: no decoding, no model."""
        keyframes = read_jsonl(self.layout.keyframes(video_id))
        for keyframe in keyframes:
            keyframe["rejected"] = self.gate.reason({name: keyframe[name] for name in MEASUREMENTS})
        self._select(keyframes)
        write_jsonl(self.layout.keyframes(video_id), keyframes)
        return {"keyframes": len(keyframes), "indexed": sum(keyframe["indexed"] for keyframe in keyframes)}

    def _select(self, keyframes: list[dict[str, Any]]) -> None:
        group = 0
        for _, members in groupby(keyframes, key=lambda keyframe: keyframe["shot_id"]):
            group = self.grouping.assign(list(members), group)

    def _keep(self, video_id: str, partial: Path, slot: Slot, decoded: DecodedFrame, image: Any,
              metrics: dict[str, float]) -> dict[str, Any]:
        keyframe_id = f"{video_id}_{decoded.index:06d}"
        partial.mkdir(parents=True, exist_ok=True)
        image.save(partial / f"{keyframe_id}.jpg", quality=self.jpeg_quality)
        return {"video_id": video_id, "keyframe_id": keyframe_id, "shot_id": slot.shot_id,
                "frame_index": decoded.index, "time_ms": decoded.time_ms, "pts": decoded.pts,
                "time_base": str(decoded.time_base), "time_source": decoded.time_source,
                "image": self.layout.frame_image(video_id, keyframe_id).relative_to(self.layout.root).as_posix(),
                **metrics, "dhash": dhash(image), "rejected": self.gate.reason(metrics), "group": None,
                "indexed": False}
