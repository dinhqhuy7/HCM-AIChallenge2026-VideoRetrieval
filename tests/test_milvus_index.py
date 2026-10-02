"""MilvusIndex on a Milvus Lite file (pymilvus 2.5 brings Milvus Lite on Linux and macOS)."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HAVE_MILVUS = all(importlib.util.find_spec(name) is not None for name in ("numpy", "pymilvus", "milvus_lite"))


def row(vector, video, index):
    return {"vector": vector, "keyframe_id": f"{video}_{index:06d}", "video_id": video, "shot_id": index // 10,
            "frame_index": index, "time_ms": index * 40}


@unittest.skipUnless(HAVE_MILVUS, "needs numpy, pymilvus and milvus-lite")
class MilvusIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One file for the class, a collection per test: each Milvus Lite file runs a server
        # until the process exits.
        cls.folder = tempfile.TemporaryDirectory()
        cls.uri = str(Path(cls.folder.name) / "index" / "milvus.db")

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def setUp(self):
        import numpy as np

        from src.retrieval.milvus_index import MilvusIndex

        self.index = MilvusIndex(self.uri, self._testMethodName)
        self.index.create(4, "AUTOINDEX", "COSINE")
        rng = np.random.default_rng(0)
        self.vectors = rng.normal(size=(40, 4)).astype(np.float32)
        self.vectors /= np.linalg.norm(self.vectors, axis=1, keepdims=True)
        rows = [row(v.tolist(), "A" if i < 20 else "B", i if i < 20 else 39 - i) for i, v in enumerate(self.vectors)]
        self.index.insert(rows)
        self.index.flush()

    def test_search_returns_cosine_similarity_best_first(self):
        import numpy as np

        hits = self.index.search(self.vectors[3], 5)
        self.assertEqual(hits[0].keyframe_id, "A_000003")
        expected = sorted((self.vectors @ self.vectors[3]).tolist(), reverse=True)[:5]
        np.testing.assert_allclose([hit.score for hit in hits], expected, atol=1e-4)

    def test_search_inside_one_video(self):
        self.assertTrue(all(hit.video_id == "B" for hit in self.index.search(self.vectors[3], 50, video_id="B")))

    def test_ids_with_quotes_and_accents(self):
        for video in ('a"b\\c', "Tập_1"):
            self.index.insert([row(self.vectors[0].tolist(), video, 0)])
        self.index.flush()
        for video in ('a"b\\c', "Tập_1"):
            self.assertEqual(self.index.keyframe_ids(video), {f"{video}_000000"})
            self.assertEqual([hit.video_id for hit in self.index.search(self.vectors[0], 50, video_id=video)], [video])

    def test_frames_of_a_video_in_time_order(self):
        import numpy as np

        frames, vectors = self.index.frames_of("B")
        self.assertEqual([f.frame_index for f in frames], list(range(20)))
        np.testing.assert_allclose(vectors[0], self.vectors[39], atol=1e-6)  # B's frame 0 was row 39
        self.assertEqual(self.index.keyframe_ids("B"), {f"B_{i:06d}" for i in range(20)})

    def test_a_video_longer_than_one_query(self):
        import numpy as np

        count = 16500  # a plain query on Milvus Lite stops at 16383 rows
        vectors = np.random.default_rng(1).normal(size=(count, 4)).astype(np.float32)
        self.index.insert([row(v.tolist(), "LONG", i) for i, v in enumerate(vectors)])
        self.index.flush()
        frames, found = self.index.frames_of("LONG")
        self.assertEqual([f.frame_index for f in frames], list(range(count)))
        self.assertEqual(found.shape, (count, 4))
        self.assertEqual(len(self.index.search(vectors[0], 20000)), 16384)  # the limit is cut to what Milvus takes

    def test_a_vector_of_the_wrong_length_is_refused_even_when_the_batch_adds_up(self):
        self.assertEqual(self.index.dim, 4)
        with self.assertRaisesRegex(ValueError, "2 numbers does not fit collection .*holds vectors of 4"):
            self.index.insert([row([1.0, 0.0], "C", 0), row([0.0, 1.0], "C", 1)])  # 4 numbers in all: divides by 4
        self.assertEqual(self.index.keyframe_ids("C"), set())

    def test_delete_one_video(self):
        self.index.delete_video("A")
        self.assertEqual(self.index.keyframe_ids("A"), set())
        self.assertEqual(len(self.index.keyframe_ids("B")), 20)

    def test_create_refuses_an_existing_collection_and_drops_a_rejected_one(self):
        from src.retrieval.milvus_index import MilvusIndex

        with self.assertRaises(FileExistsError):
            self.index.create(4, "AUTOINDEX", "COSINE")
        rejected = MilvusIndex(self.uri, "rejected")
        with self.assertRaises(Exception):
            rejected.create(4, "NO_SUCH_INDEX", "COSINE")
        self.assertFalse(rejected.exists())

    def test_what_one_process_writes_the_next_one_reads(self):
        # As build_index.py writes and exits, then search.py opens the file.
        uri = str(Path(self.folder.name) / "handover" / "milvus.db")
        start = "import sys; sys.path.insert(0, sys.argv[1]); from src.retrieval.milvus_index import MilvusIndex;"
        write = ("index = MilvusIndex(sys.argv[2], 'siglip2'); index.create(4, 'AUTOINDEX', 'COSINE');"
                 "index.insert([{'vector': [1.0, 0.0, 0.0, float(i)], 'keyframe_id': f'A_{i:06d}', 'video_id': 'A',"
                 " 'shot_id': 0, 'frame_index': i, 'time_ms': 40 * i} for i in range(3)]); index.flush()")
        read = "import numpy as np; print(len(MilvusIndex(sys.argv[2], 'siglip2').open().search(np.ones(4), 100)))"
        for code in (write, read):
            result = subprocess.run([sys.executable, "-c", start + code, str(ROOT), uri], capture_output=True,
                                    text=True, timeout=300)
            self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertEqual(result.stdout.split()[-1:], ["3"])

    def test_opening_a_missing_collection_says_what_to_run(self):
        from src.retrieval.milvus_index import MilvusIndex

        with self.assertRaisesRegex(FileNotFoundError, "run build_index.py visual first"):
            MilvusIndex(self.uri, "pe_core").open()


if __name__ == "__main__":
    unittest.main()
