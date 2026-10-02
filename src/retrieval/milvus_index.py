"""Keyframe vectors in Milvus: one collection per encoder, one row per indexed keyframe.

`uri` decides the deployment: a file path runs Milvus Lite inside this process, an address
such as http://localhost:19530 talks to Milvus standalone (docs/setup.md). The index type
and the metric come from configs/index.yaml; no index parameter is set here. Milvus Lite
keeps a file for one process until that process exits, so build_index.py and search.py must
not run on the same file at once.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.retrieval.hits import Frame

FIELDS = ["keyframe_id", "video_id", "shot_id", "frame_index", "time_ms"]


def resolve_uri(uri: str, data_root: Path) -> str:
    """A file path is taken relative to the data folder; an address is used as given."""
    return uri if "://" in uri else str(Path(data_root) / uri)


class MilvusIndex:
    MAX_LIMIT = 16384  # Milvus accepts a search limit (top-k) from 1 to 16384

    def __init__(self, uri: str, collection: str) -> None:
        from pymilvus import MilvusClient

        if "://" not in uri:
            Path(uri).parent.mkdir(parents=True, exist_ok=True)
        self.client = MilvusClient(uri)
        self.collection = collection
        self._dim: int | None = None

    def exists(self) -> bool:
        return self.client.has_collection(self.collection)

    @property
    def dim(self) -> int:
        """Length of the vectors this collection holds."""
        if self._dim is None:
            fields = self.client.describe_collection(self.collection)["fields"]
            self._dim = int(next(field["params"]["dim"] for field in fields if field["name"] == "vector"))
        return self._dim

    def create(self, dim: int, index_type: str, metric_type: str) -> None:
        from pymilvus import DataType, MilvusClient

        if self.exists():
            raise FileExistsError(f"Milvus already has a collection {self.collection!r}")
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field(field_name="keyframe_id", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="video_id", datatype=DataType.VARCHAR, max_length=128)
        schema.add_field(field_name="shot_id", datatype=DataType.INT64)
        schema.add_field(field_name="frame_index", datatype=DataType.INT64)
        schema.add_field(field_name="time_ms", datatype=DataType.INT64)
        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type=index_type, metric_type=metric_type)
        try:
            self.client.create_collection(collection_name=self.collection, schema=schema, index_params=index_params)
        except Exception:
            # Milvus makes the collection before its index: a rejected index (HNSW on Milvus Lite,
            # a misspelt type) would leave behind a collection that cannot be searched.
            if self.exists():
                self.client.drop_collection(self.collection)
            raise

    def open(self) -> "MilvusIndex":
        """Load the collection for searching (a new process must do this once)."""
        if not self.exists():
            raise FileNotFoundError(f"Milvus has no collection {self.collection!r}: run build_index.py visual first")
        self.client.load_collection(self.collection)
        return self

    def insert(self, rows: list[dict[str, Any]]) -> None:
        # Milvus Lite only checks that the numbers of the whole batch divide by the dimension, so
        # 5 vectors of 1024 numbers went into a collection of 1280 without an error.
        for row in rows:
            if len(row["vector"]) != self.dim:
                raise ValueError(f"a vector of {len(row['vector'])} numbers does not fit collection "
                                 f"{self.collection!r}, which holds vectors of {self.dim}")
        self.client.insert(self.collection, rows)

    def flush(self) -> None:
        self.client.flush(self.collection)

    def delete_video(self, video_id: str) -> None:
        self.client.delete(self.collection, filter=self._video(video_id))

    def keyframe_ids(self, video_id: str) -> set[str]:
        """The keyframes of a video that have a vector in this collection."""
        return {row["keyframe_id"] for row in self._rows(video_id, ["keyframe_id"])}

    def search(self, vector: np.ndarray, limit: int, video_id: str | None = None) -> list[Frame]:
        """Nearest keyframes, best first; ``score`` is what the metric returns (for COSINE, the
        cosine similarity)."""
        results = self.client.search(self.collection, data=[vector.tolist()], limit=min(limit, self.MAX_LIMIT),
                                     filter=self._video(video_id) if video_id else "", output_fields=FIELDS)
        return [Frame(**{name: hit["entity"][name] for name in FIELDS}, score=float(hit["distance"]))
                for hit in results[0]]

    def frames_of(self, video_id: str) -> tuple[list[Frame], np.ndarray]:
        """Every indexed keyframe of one video, in time order, with its vector."""
        rows = sorted(self._rows(video_id, FIELDS + ["vector"]), key=lambda row: row["frame_index"])
        frames = [Frame(**{name: row[name] for name in FIELDS}) for row in rows]
        vectors = np.asarray([row["vector"] for row in rows], dtype=np.float32).reshape(len(rows), -1)
        return frames, vectors

    def _rows(self, video_id: str, fields: list[str]) -> list[dict[str, Any]]:
        # An iterator: Milvus Lite cuts a plain query at 16383 rows without an error, and a long
        # video with dense keyframes has more.
        iterator = self.client.query_iterator(self.collection, batch_size=1000, filter=self._video(video_id),
                                              output_fields=fields)
        rows: list[dict[str, Any]] = []
        while batch := iterator.next():
            rows.extend(batch)
        iterator.close()
        return rows

    @staticmethod
    def _video(video_id: str) -> str:
        # json.dumps quotes and escapes the id; ensure_ascii=False because Milvus Lite does not
        # read \u escapes.
        return f"video_id == {json.dumps(video_id, ensure_ascii=False)}"
