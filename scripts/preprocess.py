"""Offline step 1: videos -> shots -> keyframes, pictures and the keyframe map.

    python scripts/preprocess.py --videos path/to/videos
    python scripts/preprocess.py --reselect          # apply new quality or grouping settings

Videos already done (their keyframe map exists) are skipped, so the command can be run
again after an interruption. Each video's frame count is checked against data/videos.csv,
the organisers' copies. See docs/offline/01-shots-and-keyframes.md.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import MissingSetting, Settings  # noqa: E402
from src.layout import DataLayout  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--videos", type=Path, help="folder searched recursively for .mp4 files")
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="output folder (default: data)")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "preprocess.yaml")
    parser.add_argument("--video", action="append", default=[], help="only this video id; repeatable")
    parser.add_argument("--device", help="overrides shots.device, e.g. cuda:1 or cpu")
    parser.add_argument("--force", action="store_true", help="redo videos that are already done")
    parser.add_argument("--reselect", action="store_true",
                        help="apply quality and grouping again to videos already done, from their measurements")
    parser.add_argument("--video-list", type=Path, default=ROOT / "data" / "videos.csv",
                        help="frame counts to check each copy against (default: data/videos.csv)")
    args = parser.parse_args()
    if args.videos is None and not args.reselect:
        parser.error("--videos is required, except with --reselect")

    settings = Settings.load(args.config)
    layout = DataLayout(args.data)

    from src.preprocess.keyframes import keyframe_policy
    from src.preprocess.pipeline import Preprocessor
    from src.preprocess.quality import grouping, quality_gate

    if args.reselect:
        done = [video for video in layout.videos() if not args.video or video in args.video]
        preprocessor = Preprocessor(layout, None, None, quality_gate(settings), grouping(settings), 0)
        for number, video_id in enumerate(done, start=1):
            print(f"[{number}/{len(done)}] {video_id}: {preprocessor.reselect(video_id)}", flush=True)
        return 0

    videos = sorted(args.videos.rglob("*.mp4"))
    if args.video:
        videos = [video for video in videos if video.stem in set(args.video)]
    todo = [video for video in videos if args.force or not layout.keyframes(video.stem).exists()]
    print(f"{len(videos)} videos, {len(todo)} to process", flush=True)
    if not todo:
        return 0

    from src.preprocess.shots import ShotDetector
    from src.preprocess.video_list import VideoList

    policy, gate, grouper = keyframe_policy(settings), quality_gate(settings), grouping(settings)
    detector = ShotDetector(float(settings.require("shots.threshold")),
                            args.device or settings.get("shots.device", "auto"))
    jpeg_quality = int(settings.require("keyframes.jpeg_quality"))
    preprocessor = Preprocessor(layout, detector, policy, gate, grouper, jpeg_quality)
    listed, failed = VideoList(args.video_list), []
    for number, video in enumerate(todo, start=1):
        began = time.time()
        try:
            summary = preprocessor.run(video, video.stem)
        except Exception as error:  # one bad video must not stop the batch
            failed.append(video.stem)
            print(f"[{number}/{len(todo)}] {video.stem}: FAILED {type(error).__name__}: {error}", flush=True)
            continue
        first_ms = summary.pop("first_frame_ms")
        print(f"[{number}/{len(todo)}] {video.stem}: {summary} in {time.time() - began:.0f}s", flush=True)
        warnings = [listed.mismatch(video.stem, summary["frames"])]
        if first_ms:
            warnings.append(f"{video.stem}: the first frame is at {first_ms} ms, not 0; all its times are "
                            "counted from the stream's own zero")
        for warning in filter(None, warnings):
            print(f"    WARNING {warning}", flush=True)
    if failed:
        print(f"{len(failed)} failed: {' '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (MissingSetting, ValueError) as error:  # a setting to fill in or a value out of range
        sys.exit(f"error: {error}")
