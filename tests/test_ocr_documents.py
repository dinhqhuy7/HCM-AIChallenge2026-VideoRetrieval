import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.layout import DataLayout, write_jsonl  # noqa: E402
from src.ocr.documents import OcrDocuments  # noqa: E402
from src.retrieval.keyword_index import KeywordIndex, Line  # noqa: E402


def keyframe(index, shot_id, indexed=True):
    return {"video_id": "V", "keyframe_id": f"V_{index:06d}", "shot_id": shot_id, "frame_index": index,
            "time_ms": index * 40, "indexed": indexed}


def reading(index, *lines):
    return {"keyframe_id": f"V_{index:06d}", "lines": [{"text": text, "score": score, "box": [0.0, 0.0, 1.0, 0.1]}
                                                        for text, score in lines]}


class OcrDocumentsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.layout = DataLayout(folder.name)
        write_jsonl(self.layout.keyframes("V"), [keyframe(0, 0), keyframe(10, 0), keyframe(20, 0), keyframe(30, 1),
                                                 keyframe(40, 2), keyframe(50, 2, indexed=False)])

    def documents(self, *readings):
        write_jsonl(self.layout.evidence("ocr", "V"), readings)
        return OcrDocuments().build(self.layout, "V")

    def test_a_caption_read_on_many_keyframes_is_one_line_in_its_best_reading(self):
        (document,) = self.documents(reading(0, ("TIN CHÍNH", 0.90)), reading(10, ("Tin  chính", 0.99)),
                                     reading(20, ("TIN CHINH", 0.95)))
        self.assertEqual((document.video_id, document.shot_id), ("V", 0))
        self.assertEqual(document.lines, [Line("Tin chính", "V_000010", 10, 400)])

    def test_different_lines_stay_apart_and_each_shot_keeps_its_own(self):
        documents = self.documents(reading(0, ("HTV9", 0.99), ("06:30:31", 0.98)), reading(10, ("HTV9", 0.99)),
                                   reading(30, ("HTV9", 0.96)))
        self.assertEqual([(d.shot_id, [line.text for line in d.lines]) for d in documents],
                         [(0, ["HTV9", "06:30:31"]), (1, ["HTV9"])])
        self.assertEqual(documents[0].lines[0].keyframe_id, "V_000000")  # a tie in score keeps the first

    def test_lines_without_words_are_dropped_and_a_shot_without_words_has_no_document(self):
        documents = self.documents(reading(0, ("|", 0.99), ("Giá vàng", 0.9)), reading(30, ("...", 0.99)),
                                   reading(40))
        self.assertEqual([(d.shot_id, [line.text for line in d.lines]) for d in documents], [(0, ["Giá vàng"])])

    def test_readings_of_keyframes_no_longer_indexed_are_left_out(self):
        documents = self.documents(reading(40, ("Thời sự", 0.9)), reading(50, ("Giá vàng", 0.99)),
                                   reading(999, ("Giá vàng", 0.99)))
        self.assertEqual([(d.shot_id, [line.text for line in d.lines]) for d in documents], [(2, ["Thời sự"])])

    def test_the_keyword_index_finds_the_shot_on_the_keyframe_that_shows_the_words(self):
        documents = self.documents(reading(0, ("HTV9", 0.99)), reading(10, ("Giá vàng tăng mạnh", 0.9)),
                                   reading(30, ("Thời tiết", 0.9)))
        (hit,) = KeywordIndex.build("ocr", documents, 1.2, 0.75).search("gia vang", 10)
        self.assertEqual((hit.shot, hit.frame.keyframe_id, hit.frame.time_ms), (("V", 0), "V_000010", 400))


if __name__ == "__main__":
    unittest.main()
