import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.layout import DataLayout, write_jsonl  # noqa: E402
from src.object_detection.documents import ObjectDocuments  # noqa: E402
from src.retrieval.keyword_index import KeywordIndex  # noqa: E402


def keyframe(index, shot_id, indexed=True):
    return {"video_id": "V", "keyframe_id": f"V_{index:06d}", "shot_id": shot_id, "frame_index": index,
            "time_ms": index * 40, "indexed": indexed}


def detected(index, *labels):
    return {"keyframe_id": f"V_{index:06d}",
            "objects": [{"label": label, "score": 0.9, "box": [0.1, 0.1, 0.2, 0.2]} for label in labels]}


class ObjectDocumentsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.layout = DataLayout(folder.name)
        write_jsonl(self.layout.keyframes("V"), [keyframe(0, 0), keyframe(10, 0), keyframe(20, 1),
                                                 keyframe(30, 2), keyframe(40, 2, indexed=False)])

    def documents(self, *records):
        write_jsonl(self.layout.evidence("objects", "V"), records)
        return {document.shot_id: [(line.text, line.keyframe_id) for line in document.lines]
                for document in ObjectDocuments().build(self.layout, "V")}

    def test_a_label_counts_as_often_as_on_its_busiest_keyframe(self):
        documents = self.documents(detected(0, "person", "person", "person", "car"),
                                   detected(10, "person", "dog", "dog"))
        self.assertEqual(documents, {0: [("car", "V_000000"), ("dog", "V_000010"), ("dog", "V_000010"),
                                         ("person", "V_000000"), ("person", "V_000000"), ("person", "V_000000")]})

    def test_a_tie_stands_on_the_earlier_keyframe(self):
        self.assertEqual(self.documents(detected(0, "bus"), detected(10, "bus")), {0: [("bus", "V_000000")]})

    def test_keyframes_not_indexed_unknown_or_empty_add_nothing(self):
        documents = self.documents(detected(20), detected(30, "boat"), detected(40, "boat", "boat"),
                                   detected(999, "boat"))
        self.assertEqual(documents, {2: [("boat", "V_000030")]})

    def test_the_keyword_index_finds_the_shot_on_the_keyframe_that_shows_the_object(self):
        write_jsonl(self.layout.evidence("objects", "V"), [detected(0, "person"), detected(10, "dog"),
                                                           detected(20, "car")])
        (hit,) = KeywordIndex.build("objects", ObjectDocuments().build(self.layout, "V"), 1.2, 0.75).search("dog", 5)
        self.assertEqual((hit.shot, hit.frame.keyframe_id), (("V", 0), "V_000010"))


if __name__ == "__main__":
    unittest.main()
