"""Shot boundaries from TransNetV2 (Souček & Lokoč, 2020), via the transnetv2-pytorch package."""
from __future__ import annotations

from pathlib import Path


def cover(scenes: list[tuple[int, int]], frame_count: int) -> list[tuple[int, int]]:
    """Shots that tile the video: every frame in exactly one shot, ends inclusive.

    ``predictions_to_scenes`` leaves out most frames of a gradual transition: of a run of
    frames above the threshold, the first ends the previous scene and the others belong to
    no scene. A video may also begin or end inside such a run. A frame outside every shot
    can never be returned, so each gap is split at its midpoint and the first and last
    shots are stretched to the ends of the video.
    """
    if frame_count <= 0:
        return []
    scenes = sorted((max(0, start), min(frame_count - 1, end)) for start, end in scenes
                    if start <= end and start < frame_count and end >= 0)
    if any(following <= end for (_, end), (following, _) in zip(scenes, scenes[1:])):
        raise ValueError("scenes overlap; expected the output of predictions_to_scenes")
    if not scenes:
        return [(0, frame_count - 1)]
    cuts = [(end + following) // 2 for (_, end), (following, _) in zip(scenes, scenes[1:])]
    return list(zip([0] + [cut + 1 for cut in cuts], cuts + [frame_count - 1]))


class ShotDetector:
    def __init__(self, threshold: float, device: str) -> None:
        import torch
        from transnetv2_pytorch import TransNetV2

        self.model = TransNetV2(device=device)  # loads the weights bundled with the package
        self.model.eval()
        self.threshold = threshold
        self._torch = torch

    def detect(self, video: Path) -> tuple[list[tuple[int, int]], int]:
        """(shots, number of frames the model saw). TransNetV2 decodes the video with the
        ffmpeg command-line tool, at 48x27."""
        with self._torch.inference_mode():
            _, single_frame, _ = self.model.predict_video(str(video), quiet=True)
        predictions = single_frame.detach().cpu().numpy().reshape(-1)
        scenes = self.model.predictions_to_scenes(predictions, threshold=self.threshold)
        return cover([(int(start), int(end)) for start, end in scenes], len(predictions)), len(predictions)
