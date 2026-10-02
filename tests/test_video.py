import importlib.util
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_PYAV = importlib.util.find_spec("av") is not None and importlib.util.find_spec("numpy") is not None


def make_video(path: Path, times_ms: list[int]) -> None:
    """A tiny MPEG-4 video whose frames are shown at exactly ``times_ms``."""
    import av
    import numpy as np

    container = av.open(str(path), "w")
    stream = container.add_stream("mpeg4", rate=25)
    stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
    stream.codec_context.time_base = Fraction(1, 1000)
    for number, pts in enumerate(times_ms):
        frame = av.VideoFrame.from_ndarray(np.full((48, 64, 3), number * 20, dtype=np.uint8), format="rgb24")
        frame.pts, frame.time_base = pts, Fraction(1, 1000)
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


@unittest.skipUnless(HAVE_PYAV, "needs PyAV and numpy")
class VideoReaderTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.folder.cleanup()

    def read(self, times_ms):
        from src.preprocess.video import VideoReader

        path = Path(self.folder.name) / "clip.mp4"
        make_video(path, times_ms)
        with VideoReader(path) as reader:
            return reader.fps, [(frame.index, frame.time_ms, frame.time_source) for frame in reader.frames()]

    def test_constant_frame_rate(self):
        fps, frames = self.read([number * 40 for number in range(10)])
        self.assertEqual(fps, 25)
        self.assertEqual(frames, [(number, number * 40, "pts") for number in range(10)])

    def test_variable_frame_rate_follows_the_timestamps(self):
        times = [0, 40, 80, 200, 240, 600, 640, 680, 1000, 1040]
        fps, frames = self.read(times)
        self.assertEqual([time for _, time, _ in frames], times)
        self.assertEqual([index for index, _, _ in frames], list(range(10)))
        self.assertNotEqual(round(Fraction(3) / fps * 1000), 200)  # index / fps would be wrong here


if __name__ == "__main__":
    unittest.main()
