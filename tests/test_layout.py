import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.layout import DataLayout, read_json, read_jsonl, write_json, write_jsonl  # noqa: E402


def keyframe(index, indexed=True):
    return {"video_id": "V", "keyframe_id": f"V_{index:06d}", "indexed": indexed}


class LayoutTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.layout = DataLayout(self.root)

    def tearDown(self):
        self.folder.cleanup()

    def test_paths(self):
        layout = DataLayout("data")
        self.assertEqual(layout.shots("L21_V001"), Path("data/shots/L21_V001.jsonl"))
        self.assertEqual(layout.keyframes("L21_V001"), Path("data/keyframes/L21_V001.jsonl"))
        self.assertEqual(layout.frame_image("L21_V001", "L21_V001_000122"),
                         Path("data/frames/L21_V001/L21_V001_000122.jpg"))
        self.assertEqual(layout.evidence("ocr", "L21_V001"), Path("data/ocr/L21_V001.jsonl"))
        self.assertEqual(layout.keyword_index("asr"), Path("data/index/keywords-asr.json"))
        self.assertEqual(layout.submissions_log(), Path("data/submissions.jsonl"))

    def test_jsonl_round_trip(self):
        path = self.root / "ocr" / "V.jsonl"
        records = [{"keyframe_id": "V_000010", "lines": [{"text": "Giá vàng tăng"}]}, {"keyframe_id": "V_000030"}]
        write_jsonl(path, records)
        self.assertEqual(read_jsonl(path), records)
        self.assertIn("Giá vàng tăng", path.read_text(encoding="utf-8"))  # stored as written, not escaped
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["V.jsonl"])  # no temporary file left

    def test_a_failed_write_keeps_the_old_file(self):
        path = self.root / "keyframes" / "V.jsonl"
        write_jsonl(path, [keyframe(10)])

        def broken():
            yield keyframe(20)
            raise RuntimeError("disk trouble")

        with self.assertRaises(RuntimeError):
            write_jsonl(path, broken())
        self.assertEqual(read_jsonl(path), [keyframe(10)])
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["V.jsonl"])

    def test_json_round_trip(self):
        path = self.root / "index" / "keywords-ocr.json"
        write_json(path, {"lane": "ocr", "k1": 1.2})
        self.assertEqual(read_json(path), {"lane": "ocr", "k1": 1.2})

    def test_videos_are_those_with_a_keyframe_map(self):
        write_jsonl(self.layout.keyframes("L21_V002"), [keyframe(1)])
        write_jsonl(self.layout.keyframes("L21_V001"), [keyframe(1)])
        (self.root / "keyframes" / "L21_V003.jsonl.tmp").write_text("half", encoding="utf-8")
        self.assertEqual(self.layout.videos(), ["L21_V001", "L21_V002"])
        self.assertEqual(DataLayout(self.root / "empty").videos(), [])

    def test_indexed_and_current_evidence(self):
        write_jsonl(self.layout.keyframes("V"), [keyframe(10), keyframe(20, indexed=False), keyframe(30)])
        self.assertEqual([k["keyframe_id"] for k in self.layout.indexed("V")], ["V_000010", "V_000030"])
        self.assertEqual(self.layout.evidence_ids("ocr", "V"), set())
        self.assertFalse(self.layout.is_current("ocr", "V"))
        write_jsonl(self.layout.evidence("ocr", "V"), [{"keyframe_id": "V_000010"}, {"keyframe_id": "V_000030"}])
        self.assertTrue(self.layout.is_current("ocr", "V"))
        write_jsonl(self.layout.keyframes("V"), [keyframe(10), keyframe(20), keyframe(30)])  # now 20 is indexed too
        self.assertFalse(self.layout.is_current("ocr", "V"))

    def test_a_video_with_nothing_indexed_needs_no_evidence(self):
        write_jsonl(self.layout.keyframes("V"), [keyframe(10, indexed=False)])
        self.assertTrue(self.layout.is_current("objects", "V"))


if __name__ == "__main__":
    unittest.main()
