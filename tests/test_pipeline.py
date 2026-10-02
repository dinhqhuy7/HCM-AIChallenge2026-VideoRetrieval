import importlib.util
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("av", "numpy", "PIL", "cv2", "yaml"))
TEXTURED = 13  # this frame carries a checkerboard, so it is the sharpest of its slot


def make_video(path: Path, count: int) -> None:
    """Frame i is flat grey at level 8 * i, so a saved picture tells which frame it is."""
    import av
    import numpy as np

    container = av.open(str(path), "w")
    stream = container.add_stream("mpeg4", rate=25)
    stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    stream.codec_context.bit_rate = 4_000_000
    for number in range(count):
        pixels = np.full((48, 64, 3), 8 * number, dtype=np.int16)
        if number == TEXTURED:
            pixels += (np.indices((48, 64)).sum(axis=0) % 2 * 80 - 40)[:, :, None]
        frame = av.VideoFrame.from_ndarray(pixels.clip(0, 255).astype(np.uint8), format="rgb24")
        frame.pts, frame.time_base = number * 40, Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


class FakeDetector:
    def __init__(self, shots, frames):
        self.shots, self.frames = shots, frames

    def detect(self, video):
        return self.shots, self.frames


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyAV, numpy, Pillow, OpenCV and PyYAML")
class PreprocessorTest(unittest.TestCase):
    def setUp(self):
        from src.layout import DataLayout
        from src.preprocess.keyframes import DenseFrames, MiddleFrame
        from src.preprocess.quality import EachFrameAlone, KeepAll

        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.video = self.root / "V.mp4"
        make_video(self.video, 30)
        self.layout = DataLayout(self.root / "data")
        self.DenseFrames, self.MiddleFrame = DenseFrames, MiddleFrame
        self.EachFrameAlone, self.KeepAll = EachFrameAlone, KeepAll

    def tearDown(self):
        self.folder.cleanup()

    def run_with(self, policy, frames=30, gate=None):
        from src.preprocess.pipeline import Preprocessor

        detector = FakeDetector([(0, 14), (15, 29)], frames)
        return Preprocessor(self.layout, detector, policy, gate or self.KeepAll(), self.EachFrameAlone(), 95).run(
            self.video, "V")

    def grey_level(self, keyframe):
        import numpy as np
        from PIL import Image

        return float(np.asarray(Image.open(self.layout.root / keyframe["image"]).convert("L")).mean())

    def test_middle_frames_and_their_records(self):
        from src.layout import read_jsonl

        summary = self.run_with(self.MiddleFrame())
        self.assertEqual(summary, {"frames": 30, "shots": 2, "keyframes": 2, "indexed": 2, "first_frame_ms": 0})
        shots = read_jsonl(self.layout.shots("V"))
        self.assertEqual([(s["start_frame"], s["end_frame"], s["start_ms"], s["end_ms"]) for s in shots],
                         [(0, 14, 0, 600), (15, 29, 600, 1200)])
        keyframes = read_jsonl(self.layout.keyframes("V"))
        self.assertEqual([(k["keyframe_id"], k["shot_id"], k["frame_index"], k["time_ms"], k["time_source"])
                          for k in keyframes], [("V_000007", 0, 7, 280, "pts"), ("V_000022", 1, 22, 880, "pts")])
        self.assertEqual(keyframes[0]["image"], "frames/V/V_000007.jpg")
        for keyframe in keyframes:  # the picture is the frame at that index
            self.assertAlmostEqual(self.grey_level(keyframe), 8 * keyframe["frame_index"], delta=3)

    def test_dense_slots_take_the_sharpest_candidate(self):
        from src.layout import read_jsonl

        self.run_with(self.DenseFrames(5, 1))
        indexes = [k["frame_index"] for k in read_jsonl(self.layout.keyframes("V"))]
        self.assertEqual(indexes, [1, 6, TEXTURED, 16, 21, 26])  # flat frames tie, so the first candidate stays

    def test_a_frame_count_mismatch_keeps_the_previous_output(self):
        from src.layout import read_jsonl
        from src.preprocess.pipeline import FrameCountMismatch

        self.run_with(self.MiddleFrame())
        before = read_jsonl(self.layout.keyframes("V"))
        with self.assertRaises(FrameCountMismatch):
            self.run_with(self.DenseFrames(5, 1), frames=31)
        self.assertEqual(read_jsonl(self.layout.keyframes("V")), before)
        self.assertEqual(sorted(p.name for p in (self.layout.root / "frames").iterdir()), ["V"])
        self.assertEqual(sorted(p.name for p in self.layout.frames("V").iterdir()), ["V_000007.jpg", "V_000022.jpg"])

    def test_reselect_applies_new_thresholds_without_decoding(self):
        from src.config import Settings
        from src.layout import read_jsonl
        from src.preprocess.pipeline import Preprocessor
        from src.preprocess.quality import Thresholds

        self.run_with(self.DenseFrames(5, 0))
        gate = Thresholds(Settings({"min_brightness": 100}))
        summary = Preprocessor(self.layout, None, None, gate, self.EachFrameAlone(), 95).reselect("V")
        keyframes = read_jsonl(self.layout.keyframes("V"))
        self.assertEqual(summary, {"keyframes": 6, "indexed": sum(k["brightness"] >= 100 for k in keyframes)})
        self.assertTrue(all((k["rejected"] == "dark") == (k["group"] is None) for k in keyframes))


if __name__ == "__main__":
    unittest.main()
