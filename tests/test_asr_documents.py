import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.asr.documents import SpeechDocuments  # noqa: E402
from src.layout import DataLayout, write_jsonl  # noqa: E402
from src.retrieval.keyword_index import KeywordIndex  # noqa: E402

# 25 frames a second; four shots that tile 9 s: [0, 2000) [2000, 5000) [5000, 8000) [8000, 9000)
SHOTS = [(0, 49), (50, 124), (125, 199), (200, 224)]
KEYFRAMES = [(12, 0, True), (37, 0, True), (63, 1, True), (113, 1, True), (150, 2, False), (213, 3, True)]


def said(start_ms, end_ms, text):
    return {"start_ms": start_ms, "end_ms": end_ms, "text": text}


class SpeechDocumentsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.layout = DataLayout(folder.name)
        write_jsonl(self.layout.shots("V"), [
            {"video_id": "V", "shot_id": number, "start_frame": first, "end_frame": last, "start_ms": first * 40,
             "end_ms": (last + 1) * 40} for number, (first, last) in enumerate(SHOTS)])
        write_jsonl(self.layout.keyframes("V"), [
            {"video_id": "V", "keyframe_id": f"V_{index:06d}", "shot_id": shot, "frame_index": index,
             "time_ms": index * 40, "indexed": indexed} for index, shot, indexed in KEYFRAMES])

    def documents(self, segments, padding_ms=0):
        write_jsonl(self.layout.evidence("asr", "V"), segments)
        return {document.shot_id: [(line.text, line.keyframe_id) for line in document.lines]
                for document in SpeechDocuments(padding_ms).build(self.layout, "V")}

    def test_a_segment_inside_one_shot_stands_on_its_nearest_keyframe(self):
        self.assertEqual(self.documents([said(100, 900, "Xin chào"), said(1300, 1700, "hôm nay")]),
                         {0: [("Xin chào", "V_000012"), ("hôm nay", "V_000037")]})

    def test_a_segment_across_a_cut_belongs_whole_to_both_shots(self):
        self.assertEqual(self.documents([said(1800, 2600, "Châu Âu nắng nóng")]),
                         {0: [("Châu Âu nắng nóng", "V_000037")], 1: [("Châu Âu nắng nóng", "V_000063")]})

    def test_a_shot_with_no_indexed_keyframe_gets_nothing(self):
        self.assertEqual(self.documents([said(5200, 5800, "không ai thấy"), said(7900, 8100, "cuối")]),
                         {3: [("cuối", "V_000213")]})

    def test_padding_reaches_the_next_shot(self):
        segments = [said(1300, 1750, "trước điểm cắt")]
        self.assertEqual(self.documents(segments), {0: [("trước điểm cắt", "V_000037")]})
        self.assertEqual(self.documents(segments, padding_ms=300),
                         {0: [("trước điểm cắt", "V_000037")], 1: [("trước điểm cắt", "V_000063")]})

    def test_a_phrase_split_by_a_cut_is_found_in_both_shots(self):
        write_jsonl(self.layout.evidence("asr", "V"), [said(1800, 2600, "Châu Âu nắng nóng"),
                                                       said(3000, 4000, "giá vàng")])
        index = KeywordIndex.build("asr", SpeechDocuments(0).build(self.layout, "V"), 1.2, 0.75)
        self.assertEqual(sorted(hit.shot for hit in index.search("châu âu", 10)), [("V", 0), ("V", 1)])


if __name__ == "__main__":
    unittest.main()
