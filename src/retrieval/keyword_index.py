"""Keyword lanes (OCR text, speech, object labels): one BM25 document per shot."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from src.layout import read_json, write_json
from src.retrieval.bm25 import BM25
from src.retrieval.hits import Frame, ShotHit
from src.retrieval.text import tokens


@dataclass(frozen=True)
class Line:
    """One piece of evidence and the keyframe it belongs to."""

    text: str
    keyframe_id: str
    frame_index: int
    time_ms: int


@dataclass
class ShotDocument:
    video_id: str
    shot_id: int
    lines: list[Line]

    def words(self) -> list[str]:
        return [word for line in self.lines for word in tokens(line.text)]


class KeywordIndex:
    def __init__(self, lane: str, documents: list[ShotDocument], bm25: BM25) -> None:
        self.lane = lane
        self.documents = documents
        self.bm25 = bm25

    @classmethod
    def build(cls, lane: str, documents: list[ShotDocument], k1: float, b: float) -> "KeywordIndex":
        """A shot with no line is left out: there is nothing in it to find."""
        documents = [document for document in documents if document.lines]
        return cls(lane, documents, BM25(k1, b).build([document.words() for document in documents]))

    def save(self, path: Path) -> None:
        write_json(path, {"lane": self.lane, "bm25": self.bm25.to_dict(),
                          "documents": [asdict(document) for document in self.documents]})

    @classmethod
    def load(cls, path: Path) -> "KeywordIndex":
        data = read_json(path)
        documents = [ShotDocument(item["video_id"], item["shot_id"], [Line(**line) for line in item["lines"]])
                     for item in data["documents"]]
        return cls(data["lane"], documents, BM25.from_dict(data["bm25"]))

    def search(self, query: str, limit: int) -> list[ShotHit]:
        """Up to ``limit`` shots, best first, each standing on the keyframe where it matched."""
        words = tokens(query)
        return [ShotHit(self._frame(self.documents[number], set(words), score), score)
                for number, score in self.bm25.search(words, limit)]

    @staticmethod
    def _frame(document: ShotDocument, words: set[str], score: float) -> Frame:
        """The keyframe whose lines hold the most query words: where the text is actually seen.
        On a tie, the earlier keyframe."""
        matches: Counter[str] = Counter()
        first: dict[str, Line] = {}
        for line in document.lines:
            first.setdefault(line.keyframe_id, line)
            matches[line.keyframe_id] += len(words & set(tokens(line.text)))
        best = max(first.values(), key=lambda line: (matches[line.keyframe_id], -line.frame_index))
        return Frame(document.video_id, document.shot_id, best.keyframe_id, best.frame_index, best.time_ms, score)
