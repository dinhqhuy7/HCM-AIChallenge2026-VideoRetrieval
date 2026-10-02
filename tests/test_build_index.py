"""scripts/build_index.py with stand-in models on two tiny videos; Milvus Lite is the real one."""
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None
                     for name in ("yaml", "numpy", "PIL", "torch", "pymilvus", "milvus_lite"))

# frame index, shot; 25 frames a second, shots [0, 2000) and [2000, 4000) ms
KEYFRAMES = [(12, 0), (37, 0), (63, 1)]
CONFIG = """
visual: {encoders: [siglip2], device: cpu, batch_size: 2, siglip2: {model: stand-in}}
milvus: {uri: index/milvus.db, index_type: AUTOINDEX, metric_type: COSINE}
ocr: {device: null}
asr: {model: stand-in, shot_padding_ms: 0}
objects: {enabled: true, weights: stand-in.pt, classes: [person]}
keywords: {k1: 1.2, b: 0.75}
"""


def load_script():
    spec = importlib.util.spec_from_file_location("build_index_script", ROOT / "scripts" / "build_index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeEncoder:
    dim = 4

    def encode_images(self, images):
        import numpy as np

        vectors = np.array([[*image.getpixel((0, 0)), 1.0] for image in images], dtype=np.float32)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class FakeReader:
    """Reads "text <keyframe>" on every picture; fails on the videos in ``fail``."""

    fail, short = set(), set()

    def __init__(self, settings, device):
        pass

    def read(self, pictures):
        video = Path(pictures[0]).parent.name if pictures else None
        if video in self.fail:
            raise RuntimeError("unreadable picture")
        for picture in pictures[:-1] if video in self.short else pictures:
            yield [{"text": f"text {Path(picture).stem}", "score": 0.9, "box": [0.0, 0.0, 1.0, 0.1]}]

    detect = read


class FakeTranscriber:
    def __init__(self, settings, device):
        pass

    def transcribe(self, video):
        return [{"start_ms": 1500, "end_ms": 2500, "text": f"speech {Path(video).stem}"}]


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy, Pillow, PyTorch, pymilvus and milvus-lite")
class BuildIndexTest(unittest.TestCase):
    def setUp(self):
        from PIL import Image

        from src.layout import DataLayout, write_jsonl

        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "data"
        self.config = Path(folder.name) / "index.yaml"
        self.config.write_text(CONFIG, encoding="utf-8")
        self.layout = DataLayout(self.root)
        for number, video in enumerate(("V1", "V2")):
            write_jsonl(self.layout.shots(video), [
                {"video_id": video, "shot_id": 0, "start_frame": 0, "end_frame": 49, "start_ms": 0, "end_ms": 2000},
                {"video_id": video, "shot_id": 1, "start_frame": 50, "end_frame": 99, "start_ms": 2000,
                 "end_ms": 4000}])
            for index, _ in KEYFRAMES:
                path = self.layout.frame_image(video, f"{video}_{index:06d}")
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (32, 24), (40 * number + 10, index * 3, 200)).save(path)
            self.write_map(video)
        FakeReader.fail, FakeReader.short = set(), set()
        self.script = load_script()

    def write_map(self, video, unindexed=()):
        from src.layout import write_jsonl

        write_jsonl(self.layout.keyframes(video), [
            {"video_id": video, "keyframe_id": f"{video}_{index:06d}", "shot_id": shot, "frame_index": index,
             "time_ms": index * 40, "image": f"frames/{video}/{video}_{index:06d}.jpg",
             "indexed": index not in unindexed} for index, shot in KEYFRAMES])

    def run_step(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = self.script.main([*argv, "--data", str(self.root), "--config", str(self.config)])
        return code, output.getvalue()

    def evidence(self, kind, video):
        from src.layout import read_jsonl

        return read_jsonl(self.layout.evidence(kind, video))

    def test_visual_embeds_the_indexed_keyframes_and_redoes_a_video_only_when_they_change(self):
        from src.retrieval.milvus_index import MilvusIndex

        with mock.patch("src.embeddings.load_encoder", return_value=FakeEncoder()):
            self.assertEqual(self.run_step("visual")[0], 0)
            self.write_map("V2", unindexed={37})
            code, output = self.run_step("visual")
        self.assertEqual(code, 0)
        self.assertIn("siglip2: 1 of 2 videos to embed", output)
        self.assertIn("[1/1] V2: 2 vectors", output)
        index = MilvusIndex(str(self.root / "index" / "milvus.db"), "siglip2").open()
        self.assertEqual(index.keyframe_ids("V1"), {"V1_000012", "V1_000037", "V1_000063"})
        self.assertEqual(index.keyframe_ids("V2"), {"V2_000012", "V2_000063"})
        frames, vectors = index.frames_of("V2")
        self.assertEqual([(f.shot_id, f.frame_index, f.time_ms) for f in frames], [(0, 12, 480), (1, 63, 2520)])
        self.assertEqual(vectors.shape, (2, 4))

    def test_visual_refuses_a_model_whose_vectors_do_not_fit_the_collection(self):
        class Wider(FakeEncoder):
            dim = 6

        with mock.patch("src.embeddings.load_encoder", return_value=FakeEncoder()):
            self.assertEqual(self.run_step("visual")[0], 0)
        with mock.patch("src.embeddings.load_encoder", return_value=Wider()):
            with self.assertRaisesRegex(ValueError, "holds vectors of 4 numbers, but this model gives 6"):
                self.run_step("visual", "--force")

    def test_ocr_writes_one_record_per_indexed_keyframe_and_skips_what_is_current(self):
        with mock.patch("src.ocr.reader.OcrReader", FakeReader):
            code, output = self.run_step("ocr")
            self.assertEqual(code, 0)
            self.assertIn("[1/2] V1: 3 lines on 3 keyframes", output)
            self.assertEqual(self.evidence("ocr", "V1")[1], {"keyframe_id": "V1_000037", "lines": [
                {"text": "text V1_000037", "score": 0.9, "box": [0.0, 0.0, 1.0, 0.1]}]})
            self.assertIn("ocr: 0 of 2 videos to do", self.run_step("ocr")[1])
            self.assertIn("ocr: 2 of 2 videos to do", self.run_step("ocr", "--force")[1])
            self.write_map("V1", unindexed={12})
            code, output = self.run_step("ocr")
        self.assertIn("ocr: 1 of 2 videos to do", output)
        self.assertEqual([record["keyframe_id"] for record in self.evidence("ocr", "V1")], ["V1_000037", "V1_000063"])

    def test_a_video_that_fails_is_reported_its_old_file_kept_and_the_others_go_on(self):
        with mock.patch("src.ocr.reader.OcrReader", FakeReader):
            self.run_step("ocr")
            before = self.layout.evidence("ocr", "V1").read_text(encoding="utf-8")
            FakeReader.fail, FakeReader.short = {"V1"}, {"V2"}
            code, output = self.run_step("ocr", "--force")
        self.assertEqual(code, 1)
        self.assertIn("V1: FAILED RuntimeError: unreadable picture", output)
        self.assertIn("V2: FAILED ValueError", output)  # one picture short: zip(strict=True)
        self.assertIn("2 failed: V1 V2", output)
        self.assertEqual(self.layout.evidence("ocr", "V1").read_text(encoding="utf-8"), before)
        self.assertEqual(sorted(path.name for path in (self.root / "ocr").iterdir()), ["V1.jsonl", "V2.jsonl"])

    def test_objects_follow_the_same_rules_and_stop_when_disabled(self):
        with mock.patch("src.object_detection.detector.ObjectDetector", FakeReader):
            code, output = self.run_step("objects")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.evidence("objects", "V2")), 3)
        self.config.write_text(CONFIG.replace("enabled: true", "enabled: false"), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "objects.enabled is false"):
            self.run_step("objects")

    def test_asr_needs_the_video_files_and_transcribes_each_once(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.run_step("asr")
        videos = self.root.parent / "videos"
        (videos / "L01").mkdir(parents=True)
        (videos / "L01" / "V1.mp4").write_bytes(b"")
        with mock.patch("src.asr.transcriber.Transcriber", FakeTranscriber):
            with self.assertRaisesRegex(SystemExit, "no video file .* for: V2"):
                self.run_step("asr", "--videos", str(videos))
            (videos / "L01" / "V2.mp4").write_bytes(b"")
            code, output = self.run_step("asr", "--videos", str(videos))
            self.assertEqual(code, 0)
            self.assertIn("asr: 0 of 2 videos to do", self.run_step("asr", "--videos", str(videos))[1])
        self.assertEqual(self.evidence("asr", "V2"), [{"start_ms": 1500, "end_ms": 2500, "text": "speech V2"}])

    def test_keywords_index_every_lane_with_evidence_and_warn_about_stale_files(self):
        from src.retrieval.keyword_index import KeywordIndex

        with mock.patch("src.ocr.reader.OcrReader", FakeReader), \
                mock.patch("src.asr.transcriber.Transcriber", FakeTranscriber):
            self.run_step("ocr")
            videos = self.root.parent / "videos"
            videos.mkdir()
            for video in ("V1", "V2"):
                (videos / f"{video}.mp4").write_bytes(b"")
            self.run_step("asr", "--videos", str(videos))
        self.write_map("V2", unindexed={63})
        code, output = self.run_step("keywords")
        self.assertEqual(code, 0)
        self.assertIn("ocr: WARNING 1 videos have evidence for other keyframes than the indexed ones (V2)", output)
        self.assertIn("objects: no evidence yet, skipped", output)
        self.assertIn("asr: 3 shot documents from 2 videos", output)  # V2's shot 1 has no indexed keyframe
        (hit,) = KeywordIndex.load(self.layout.keyword_index("asr")).search("speech v2", 5)[:1]
        self.assertEqual((hit.shot, hit.frame.keyframe_id), (("V2", 0), "V2_000037"))
        ocr = KeywordIndex.load(self.layout.keyword_index("ocr"))
        self.assertEqual(ocr.search("V2_000063", 5), [])  # a reading of a keyframe no longer indexed


if __name__ == "__main__":
    unittest.main()
