"""Offline steps 2-6: keyframes -> vectors in Milvus, and evidence -> keyword indexes.

    python scripts/build_index.py visual                       # main environment
    python scripts/build_index.py ocr                          # OCR environment
    python scripts/build_index.py asr --videos path/to/videos  # main environment
    python scripts/build_index.py objects                      # objects environment (optional)
    python scripts/build_index.py keywords                     # any environment

A step redoes a video whose output no longer matches the video's indexed keyframes (after
preprocess.py --force or --reselect, for example) and skips the others; --force redoes them
anyway. A video that fails is reported and the others go on. Run `keywords` after ocr, asr or
objects: it rebuilds each lane's BM25 index from the evidence of every video. With Milvus Lite,
do not run `visual` while search.py has the file open. See docs/offline/.
"""
from __future__ import annotations

import argparse
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import MissingSetting, Settings  # noqa: E402
from src.layout import DataLayout, write_jsonl  # noqa: E402


class Step(ABC):
    def __init__(self, layout: DataLayout, settings: Settings, args: argparse.Namespace) -> None:
        self.layout, self.settings, self.args = layout, settings, args
        self.videos = [video for video in layout.videos() if not args.video or video in args.video]

    @abstractmethod
    def run(self) -> list[str]:
        """Do the step; returns the videos that failed."""

    @staticmethod
    def each(todo: list[str], work: Callable[[str], str]) -> list[str]:
        """``work`` on every video, printing what it did; a video that fails is reported and
        the others go on."""
        failed = []
        for number, video_id in enumerate(todo, start=1):
            began = time.time()
            try:
                done = work(video_id)
            except Exception as error:  # one bad video must not stop the batch
                failed.append(video_id)
                print(f"[{number}/{len(todo)}] {video_id}: FAILED {type(error).__name__}: {error}", flush=True)
                continue
            print(f"[{number}/{len(todo)}] {video_id}: {done} in {time.time() - began:.0f}s", flush=True)
        return failed


class VisualStep(Step):
    """Embed the indexed keyframes with every encoder listed in visual.encoders."""

    def run(self) -> list[str]:
        from src.embeddings import load_encoder
        from src.retrieval.milvus_index import FIELDS, MilvusIndex, resolve_uri

        device = self.args.device or self.settings.get("visual.device", "cuda")
        uri = resolve_uri(self.settings.require("milvus.uri"), self.layout.root)
        batch_size = int(self.settings.require("visual.batch_size"))
        failed = []
        for name in self.settings.require("visual.encoders"):
            index = MilvusIndex(uri, name)
            if index.exists():
                index.open()
            todo = [video for video in self.videos if self.args.force or not self.current(index, video)]
            print(f"{name}: {len(todo)} of {len(self.videos)} videos to embed", flush=True)
            if not todo:
                continue
            encoder = load_encoder(name, self.settings, device)
            if not index.exists():
                index.create(encoder.dim, self.settings.require("milvus.index_type"),
                             self.settings.require("milvus.metric_type"))
            elif index.dim != encoder.dim:
                raise ValueError(f"collection {name!r} holds vectors of {index.dim} numbers, but this model gives "
                                 f"{encoder.dim}: the model changed. Use another milvus.uri, or drop the collection "
                                 "and build it again")

            def embed(video_id: str) -> str:
                keyframes = self.layout.indexed(video_id)
                # Stale vectors go first; a video stopped halfway no longer matches its keyframes,
                # so the next run does it again.
                index.delete_video(video_id)
                for first in range(0, len(keyframes), batch_size):
                    batch = keyframes[first:first + batch_size]
                    vectors = encoder.encode_images([picture(self.layout.root / keyframe["image"])
                                                     for keyframe in batch])
                    index.insert([{"vector": vector.tolist(), **{field: keyframe[field] for field in FIELDS}}
                                  for keyframe, vector in zip(batch, vectors, strict=True)])
                index.flush()
                return f"{len(keyframes)} vectors"

            failed += self.each(todo, embed)
            del encoder
            release_gpu()
        return failed

    def current(self, index: Any, video_id: str) -> bool:
        wanted = {keyframe["keyframe_id"] for keyframe in self.layout.indexed(video_id)}
        return index.exists() and index.keyframe_ids(video_id) == wanted


class KeyframeStep(Step):
    """A step that looks at every indexed keyframe and writes one record per keyframe."""

    kind: str
    field: str

    def todo(self) -> list[str]:
        todo = [video for video in self.videos if self.args.force or not self.layout.is_current(self.kind, video)]
        print(f"{self.kind}: {len(todo)} of {len(self.videos)} videos to do", flush=True)
        return todo

    def write(self, video_id: str, keyframes: list[dict[str, Any]], found: Iterable[list[dict[str, Any]]]) -> int:
        """Write the records as they come; returns how many items were found. A reader that
        gives fewer or more pictures than asked fails the video, and its old file stays."""
        count = 0

        def records() -> Iterable[dict[str, Any]]:
            nonlocal count
            for keyframe, items in zip(keyframes, found, strict=True):
                count += len(items)
                yield {"keyframe_id": keyframe["keyframe_id"], self.field: items}

        write_jsonl(self.layout.evidence(self.kind, video_id), records())
        return count


class OcrStep(KeyframeStep):
    kind, field = "ocr", "lines"

    def run(self) -> list[str]:
        todo = self.todo()
        if not todo:
            return []
        from src.ocr.reader import OcrReader

        reader = OcrReader(self.settings.section("ocr"), self.args.device)

        def read(video_id: str) -> str:
            keyframes = self.layout.indexed(video_id)
            count = self.write(video_id, keyframes, reader.read([self.layout.root / k["image"] for k in keyframes]))
            return f"{count} lines on {len(keyframes)} keyframes"

        return self.each(todo, read)


class ObjectStep(KeyframeStep):
    kind, field = "objects", "objects"

    def run(self) -> list[str]:
        if not self.settings.get("objects.enabled"):
            raise SystemExit(f"{self.settings.source}: objects.enabled is false")
        todo = self.todo()
        if not todo:
            return []
        from src.object_detection.detector import ObjectDetector

        detector = ObjectDetector(self.settings.section("objects"), self.args.device)

        def detect(video_id: str) -> str:
            keyframes = self.layout.indexed(video_id)
            count = self.write(video_id, keyframes, detector.detect([self.layout.root / k["image"] for k in keyframes]))
            return f"{count} objects on {len(keyframes)} keyframes"

        return self.each(todo, detect)


class AsrStep(Step):
    """Speech depends on the video file only, not on its keyframes."""

    def run(self) -> list[str]:
        files = {path.stem: path for path in self.args.videos.rglob("*.mp4")}
        todo = [video for video in self.videos if self.args.force or not self.layout.evidence("asr", video).exists()]
        missing = [video for video in todo if video not in files]
        if missing:
            raise SystemExit(f"no video file under {self.args.videos} for: {' '.join(missing)}")
        print(f"asr: {len(todo)} of {len(self.videos)} videos to do", flush=True)
        if not todo:
            return []
        from src.asr.transcriber import Transcriber

        transcriber = Transcriber(self.settings.section("asr"), self.args.device)

        def transcribe(video_id: str) -> str:
            segments = transcriber.transcribe(files[video_id])
            write_jsonl(self.layout.evidence("asr", video_id), segments)
            return f"{len(segments)} segments"

        return self.each(todo, transcribe)


class KeywordStep(Step):
    """Rebuild the BM25 index of every lane that has evidence, from all videos."""

    def run(self) -> list[str]:
        from src.asr.documents import SpeechDocuments
        from src.object_detection.documents import ObjectDocuments
        from src.ocr.documents import OcrDocuments
        from src.retrieval.keyword_index import KeywordIndex

        k1, b = float(self.settings.require("keywords.k1")), float(self.settings.require("keywords.b"))
        builders = [OcrDocuments(), SpeechDocuments(int(self.settings.get("asr.shot_padding_ms", 0))),
                    ObjectDocuments()]
        for builder in builders:
            ready = [video for video in self.layout.videos() if self.layout.evidence(builder.lane, video).exists()]
            if not ready:
                print(f"{builder.lane}: no evidence yet, skipped", flush=True)
                continue
            if builder.lane != "asr":
                stale = [video for video in ready if not self.layout.is_current(builder.lane, video)]
                if stale:
                    print(f"{builder.lane}: WARNING {len(stale)} videos have evidence for other keyframes than "
                          f"the indexed ones ({' '.join(stale[:5])}); run build_index.py {builder.lane} first",
                          flush=True)
            began = time.time()
            documents = [document for video in ready for document in builder.build(self.layout, video)]
            KeywordIndex.build(builder.lane, documents, k1, b).save(self.layout.keyword_index(builder.lane))
            print(f"{builder.lane}: {len(documents)} shot documents from {len(ready)} videos in "
                  f"{time.time() - began:.0f}s", flush=True)
        return []


def picture(path: Path) -> Any:
    from PIL import Image

    with Image.open(path) as image:
        return image.convert("RGB")


def release_gpu() -> None:
    """Free the card before the next model is loaded onto it."""
    import gc

    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


STEPS: dict[str, type[Step]] = {"visual": VisualStep, "ocr": OcrStep, "asr": AsrStep,
                                "objects": ObjectStep, "keywords": KeywordStep}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("--data", type=Path, default=ROOT / "data", help="the data folder (default: data)")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "index.yaml")
    parser.add_argument("--videos", type=Path, help="folder searched recursively for .mp4 files (asr only)")
    parser.add_argument("--video", action="append", default=[],
                        help="only this video id; repeatable (keywords always uses every video)")
    parser.add_argument("--device", help="overrides the step's device, e.g. cuda:1 or cpu")
    parser.add_argument("--force", action="store_true", help="redo videos whose output is current")
    args = parser.parse_args(argv)
    if args.step == "asr" and args.videos is None:
        parser.error("asr needs --videos, the folder with the video files")

    failed = STEPS[args.step](DataLayout(args.data), Settings.load(args.config), args).run()
    if failed:
        print(f"{len(failed)} failed: {' '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (MissingSetting, ValueError) as error:  # a setting to fill in or a value out of range
        sys.exit(f"error: {error}")
