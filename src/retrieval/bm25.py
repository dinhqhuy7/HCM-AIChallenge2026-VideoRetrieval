"""Okapi BM25 over shot documents.

    score(d, q) = sum over the distinct query words w of
                  idf(w) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * |d| / avgdl))
    idf(w)      = ln(1 + (N - n(w) + 0.5) / (n(w) + 0.5))       (Lucene's form, never negative)

Robertson & Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond" (2009).
k1 and b come from configs/index.yaml; Lucene and Elasticsearch default to 1.2 and 0.75.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any


class BM25:
    def __init__(self, k1: float, b: float) -> None:
        self.k1 = float(k1)
        self.b = float(b)
        self.postings: dict[str, list[tuple[int, int]]] = {}
        self.lengths: list[int] = []

    def build(self, documents: list[list[str]]) -> "BM25":
        """``documents``: the words of each document, in order; a document's number is its position."""
        postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for number, words in enumerate(documents):
            for word, count in Counter(words).items():
                postings[word].append((number, count))
        self.postings = dict(postings)
        self.lengths = [len(words) for words in documents]
        return self

    def search(self, query: list[str], limit: int) -> list[tuple[int, float]]:
        """The ``limit`` best documents as (document number, score), best first. Only documents
        that contain at least one query word are returned."""
        count = len(self.lengths)
        if not count:
            return []
        average = sum(self.lengths) / count or 1.0
        scores: dict[int, float] = defaultdict(float)
        for word in set(query):
            postings = self.postings.get(word, [])
            if not postings:
                continue
            idf = math.log(1 + (count - len(postings) + 0.5) / (len(postings) + 0.5))
            for number, frequency in postings:
                norm = self.k1 * (1 - self.b + self.b * self.lengths[number] / average)
                scores[number] += idf * frequency * (self.k1 + 1) / (frequency + norm)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return ranked[:limit]

    def to_dict(self) -> dict[str, Any]:
        return {"k1": self.k1, "b": self.b, "lengths": self.lengths,
                "postings": {word: [list(pair) for pair in pairs] for word, pairs in self.postings.items()}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BM25":
        index = cls(data["k1"], data["b"])
        index.lengths = list(data["lengths"])
        index.postings = {word: [tuple(pair) for pair in pairs] for word, pairs in data["postings"].items()}
        return index
