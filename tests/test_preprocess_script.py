"""scripts/preprocess.py run as a command, without a model: --reselect, and its errors."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "preprocess.py"
HAVE_LIBRARIES = all(importlib.util.find_spec(name) is not None for name in ("yaml", "numpy", "PIL"))


def keyframe(index, brightness):
    return {"video_id": "V", "keyframe_id": f"V_{index:06d}", "shot_id": 0, "frame_index": index,
            "sharpness": 100.0, "brightness": brightness, "entropy": 7.0, "dhash": "0" * 16,
            "rejected": None, "group": index, "indexed": True}


@unittest.skipUnless(HAVE_LIBRARIES, "needs PyYAML, numpy and Pillow")
class PreprocessScriptTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.config = self.root / "preprocess.yaml"

    def tearDown(self):
        self.folder.cleanup()

    def run_script(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPT), "--data", str(self.root / "data"), *arguments],
                              capture_output=True, text=True, timeout=120)

    def test_reselect_applies_the_config_to_done_videos(self):
        (self.root / "data" / "keyframes").mkdir(parents=True)
        (self.root / "data" / "keyframes" / "V.jsonl").write_text(
            "\n".join(json.dumps(keyframe(i, b)) for i, b in ((10, 5.0), (20, 120.0))) + "\n", encoding="utf-8")
        self.config.write_text("quality:\n  enabled: true\n  min_brightness: 10\n", encoding="utf-8")
        result = self.run_script("--reselect", "--config", str(self.config))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[1/1] V: {'keyframes': 2, 'indexed': 1}", result.stdout)
        rows = [json.loads(line) for line in (self.root / "data" / "keyframes" / "V.jsonl").read_text().splitlines()]
        self.assertEqual([(row["rejected"], row["indexed"]) for row in rows], [("dark", False), (None, True)])

    def test_videos_are_required_unless_reselecting(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--videos is required", result.stderr)

    def test_a_folder_without_videos(self):
        (self.root / "videos").mkdir()
        result = self.run_script("--videos", str(self.root / "videos"))
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "0 videos, 0 to process"))

    def test_a_missing_setting_is_one_line(self):
        self.config.write_text("grouping:\n  enabled: true\n", encoding="utf-8")
        result = self.run_script("--reselect", "--config", str(self.config))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip().splitlines(),
                         [f"error: {self.config}: set `grouping.max_distance` -- no published default; "
                          "see docs/offline/01-shots-and-keyframes.md"])


if __name__ == "__main__":
    unittest.main()
