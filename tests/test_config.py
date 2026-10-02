import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import MissingSetting, Settings  # noqa: E402

YAML = """\
fusion:
  rrf_k: null
shots:
  threshold: 0.5
  device: auto
quality:
  enabled: false
  min_brightness: 0
asr:
  language: vi
  drop_phrases: [đăng ký kênh]
"""


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "settings.yaml"
        self.path.write_text(YAML, encoding="utf-8")
        self.settings = Settings.load(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def test_dotted_keys(self):
        self.assertEqual(self.settings.get("shots.threshold"), 0.5)
        self.assertEqual(self.settings.get("asr.drop_phrases"), ["đăng ký kênh"])

    def test_null_and_absent_read_as_the_default(self):
        self.assertIsNone(self.settings.get("fusion.rrf_k"))
        self.assertEqual(self.settings.get("fusion.rrf_k", 60), 60)
        self.assertEqual(self.settings.get("fusion.missing", "x"), "x")
        self.assertEqual(self.settings.get("shots.threshold.deeper", "x"), "x")

    def test_false_and_zero_are_values(self):
        self.assertIs(self.settings.get("quality.enabled", True), False)
        self.assertEqual(self.settings.require("quality.min_brightness"), 0)

    def test_require_names_the_file_and_the_key(self):
        with self.assertRaises(MissingSetting) as caught:
            self.settings.require("fusion.rrf_k", "the RRF paper uses 60")
        self.assertEqual(str(caught.exception), f"{self.path}: set `fusion.rrf_k` -- the RRF paper uses 60")

    def test_section(self):
        asr = self.settings.section("asr")
        self.assertEqual(asr.get("language"), "vi")
        self.assertEqual(asr.source, f"{self.path}:asr")
        self.assertEqual(self.settings.section("absent").to_dict(), {})
        with self.assertRaises(ValueError):
            self.settings.section("shots.threshold")

    def test_to_dict_is_a_copy(self):
        values = self.settings.to_dict()
        values["asr"]["drop_phrases"].append("changed")
        self.assertEqual(self.settings.get("asr.drop_phrases"), ["đăng ký kênh"])

    def test_empty_and_malformed_files(self):
        self.path.write_text("", encoding="utf-8")
        self.assertEqual(Settings.load(self.path).to_dict(), {})
        self.path.write_text("- a\n- b\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            Settings.load(self.path)


if __name__ == "__main__":
    unittest.main()
