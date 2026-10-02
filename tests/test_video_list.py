import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.preprocess.video_list import VideoList  # noqa: E402


class VideoListTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "videos.csv"
        self.path.write_text("video_id,youtube_id,fps,frames\nL30_V031,IGK0b-SsBT8,25,3499\n", encoding="utf-8")

    def tearDown(self):
        self.folder.cleanup()

    def test_matching_and_differing_copies(self):
        listed = VideoList(self.path)
        self.assertIsNone(listed.mismatch("L30_V031", 3499))
        self.assertEqual(listed.mismatch("L30_V031", 3500),
                         "L30_V031: this copy has 3500 frames, the organisers' copy has 3499 (25 fps); "
                         "its frame numbers will not match their answers")

    def test_what_cannot_be_checked_is_not_flagged(self):
        self.assertIsNone(VideoList(self.path).mismatch("X99_V001", 10))
        self.assertIsNone(VideoList(Path(self.folder.name) / "missing.csv").mismatch("L30_V031", 1))

    def test_the_list_in_the_repository(self):
        listed = VideoList(ROOT / "data" / "videos.csv")
        self.assertEqual(len(listed.rows), 873)
        row = listed.rows["L21_V001"]
        self.assertEqual((row["url"], row["fps"], row["frames"]),
                         ("https://www.youtube.com/watch?v=Rzpw5WR7nAY", "30", "37849"))


if __name__ == "__main__":
    unittest.main()
