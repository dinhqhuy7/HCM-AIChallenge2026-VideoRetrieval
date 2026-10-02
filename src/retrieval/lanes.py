"""A lane answers one kind of query with a ranking of shots.

visual   the query text against the keyframe vectors in Milvus
ocr      the query words against the text read on screen
asr      the query words against what was said
objects  the query words against the detected object labels
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np

from src.embeddings.base import Encoder
from src.retrieval.hits import ShotHit, group_by_shot
from src.retrieval.keyword_index import KeywordIndex
from src.retrieval.milvus_index import MilvusIndex


class Lane(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, depth: int) -> list[ShotHit]:
        """Up to ``depth`` shots, best first."""


class VisualLane(Lane):
    name = "visual"

    def __init__(self, encoder: Encoder, index: MilvusIndex,
                 translate: Callable[[str], str] | None = None) -> None:
        self.encoder = encoder
        self.index = index
        self.translate = translate

    def embed(self, query: str) -> np.ndarray:
        """The query as a vector, in English when a translator is given."""
        return self.encoder.encode_texts([self.translate(query) if self.translate else query])[0]

    def search(self, query: str, depth: int) -> list[ShotHit]:
        if depth < 1:
            return []
        # Frames of one shot crowd each other out, so widen the frame search until it covers
        # `depth` shots -- or until the index runs out of frames, or reaches its own limit.
        vector, limit = self.embed(query), depth
        while True:
            frames = self.index.search(vector, limit)
            shots = group_by_shot(frames)
            if len(shots) >= depth or len(frames) < limit or limit >= self.index.MAX_LIMIT:
                return shots[:depth]
            limit = min(limit * 2, self.index.MAX_LIMIT)


class KeywordLane(Lane):
    def __init__(self, index: KeywordIndex) -> None:
        self.index = index
        self.name = index.lane

    def search(self, query: str, depth: int) -> list[ShotHit]:
        return self.index.search(query, depth) if depth >= 1 else []
