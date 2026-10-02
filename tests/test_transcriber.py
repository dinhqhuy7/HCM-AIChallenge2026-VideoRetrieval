"""Transcriber with a stand-in model, and a real Whisper model when WHISPER_MODEL is set
(a name such as large-v3, or a local folder):

    WHISPER_MODEL=large-v3 python -m unittest tests.test_transcriber
"""
import importlib.util
import os
import sys
import tempfile
import unittest
import wave
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("av", "numpy", "yaml"))


def make_audio(path, start_ms):
    """One second of silence whose first sample is at ``start_ms`` on the file's clock."""
    import av
    import numpy as np

    container = av.open(str(path), "w")
    stream = container.add_stream("pcm_s16le", rate=16000, layout="mono")
    frame = av.AudioFrame.from_ndarray(np.zeros((1, 16000), dtype=np.int16), format="s16", layout="mono")
    frame.sample_rate, frame.pts, frame.time_base = 16000, start_ms * 16, Fraction(1, 16000)
    for packet in [*stream.encode(frame), *stream.encode()]:
        container.mux(packet)
    container.close()


def make_silent_video(path):
    """A few frames of picture and no audio track."""
    import av
    import numpy as np

    container = av.open(str(path), "w")
    stream = container.add_stream("mpeg4", rate=25)
    stream.width, stream.height, stream.pix_fmt = 64, 48, "yuv420p"
    for number in range(3):
        frame = av.VideoFrame.from_ndarray(np.zeros((48, 64, 3), dtype=np.uint8), format="rgb24")
        frame.pts = number
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()


class FakeModel:
    def __init__(self, segments):
        self.segments = segments
        self.calls = []

    def transcribe(self, audio, **options):
        self.calls.append((audio, options))
        return (SimpleNamespace(start=start, end=end, text=text) for start, end, text in self.segments), None


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyAV, numpy and PyYAML")
class TranscriberTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def transcriber(self, segments, drop=()):
        from src.asr.transcriber import Transcriber

        transcriber = Transcriber.__new__(Transcriber)  # no model: the stand-in answers
        transcriber.model, transcriber.options, transcriber.drop = FakeModel(segments), {"language": "vi"}, list(drop)
        return transcriber

    def test_every_key_but_its_own_goes_to_transcribe_and_null_keeps_the_default(self):
        from src.asr.transcriber import transcribe_options
        from src.config import Settings

        settings = Settings({"model": "large-v3", "device": "cuda:1", "compute_type": None, "drop_phrases": [],
                             "shot_padding_ms": 0, "language": "vi", "vad_filter": True, "beam_size": None})
        self.assertEqual(transcribe_options(settings), {"language": "vi", "vad_filter": True})

    def test_whisper_device_names(self):
        from src.asr.transcriber import whisper_device

        self.assertEqual([whisper_device(name) for name in ("cuda:1", "cuda", "cpu", "auto")],
                         [("cuda", 1), ("cuda", 0), ("cpu", 0), ("auto", 0)])

    def test_segments_in_milliseconds_tidied_and_filtered(self):
        clip = self.folder / "clip.wav"
        make_audio(clip, 0)
        transcriber = self.transcriber([(0.0, 1.2344, " Xin  chào "), (1.2344, 2.5006, "  "),
                                        (2.5006, 4.0, "Hãy ĐĂNG KÝ KÊNH nhé"), (4.0, 6.75, "Bản tin thời sự")],
                                       drop=["đăng ký kênh"])
        self.assertEqual(transcriber.transcribe(clip), [
            {"start_ms": 0, "end_ms": 1234, "text": "Xin chào"},
            {"start_ms": 4000, "end_ms": 6750, "text": "Bản tin thời sự"},
        ])
        self.assertEqual(transcriber.model.calls, [(str(clip), {"language": "vi"})])

    def test_times_are_on_the_file_clock_when_the_audio_starts_late(self):
        from src.asr.transcriber import audio_start_ms

        clip = self.folder / "late.mkv"
        make_audio(clip, 1500)
        self.assertEqual(audio_start_ms(clip), 1500.0)
        self.assertEqual(self.transcriber([(0.0, 1.0, "Xin chào")]).transcribe(clip),
                         [{"start_ms": 1500, "end_ms": 2500, "text": "Xin chào"}])

    def test_a_file_without_audio_has_no_speech(self):
        clip = self.folder / "silent.mp4"
        make_silent_video(clip)
        transcriber = self.transcriber([(0.0, 1.0, "never read")])
        self.assertEqual(transcriber.transcribe(clip), [])
        self.assertEqual(transcriber.model.calls, [])


@unittest.skipUnless(importlib.util.find_spec("faster_whisper") and os.environ.get("WHISPER_MODEL"),
                     "set WHISPER_MODEL to run a real model")
class WhisperModelTest(unittest.TestCase):
    def test_silence_gives_no_segment_with_the_vad_on(self):
        from src.asr.transcriber import Transcriber
        from src.config import Settings

        with tempfile.TemporaryDirectory() as folder:
            silence = Path(folder) / "silence.wav"
            with wave.open(str(silence), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes(b"\0\0" * 16000 * 5)
            settings = Settings({"model": os.environ["WHISPER_MODEL"], "language": "vi", "vad_filter": True})
            self.assertEqual(Transcriber(settings, os.environ.get("TEST_DEVICE", "cpu")).transcribe(silence), [])


if __name__ == "__main__":
    unittest.main()
