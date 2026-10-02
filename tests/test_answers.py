import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.submission.answers import KisAnswer, QaAnswer, TrakeAnswer, write_csv  # noqa: E402


class AnswerShapesTest(unittest.TestCase):
    def test_kis_is_a_frame_in_the_csv_and_a_time_in_dres(self):
        answer = KisAnswer("L21_V001", 1500, 60000)
        self.assertEqual(answer.csv_row(0), ["L21_V001", "1500"])
        self.assertEqual(answer.csv_row(1), ["L21_V001", "1501"])  # the base moves the frame, not the time
        self.assertEqual(answer.dres(1), {"mediaItemName": "L21_V001", "start": 60000, "end": 60000})

    def test_qa_adds_the_answer_and_dres_joins_the_parts_with_dashes(self):
        answer = QaAnswer("L21_V001", 1500, 60000, "  hai   người ")
        self.assertEqual(answer.answer, "hai người")
        self.assertEqual(answer.csv_row(0), ["L21_V001", "1500", "hai người"])
        self.assertEqual(answer.dres(5), {"text": "QA-hai người-L21_V001-60000"})

    def test_trake_is_frame_numbers_in_both(self):
        answer = TrakeAnswer("L21_V001", (100, 250, 400))
        self.assertEqual(answer.csv_row(0), ["L21_V001", "100", "250", "400"])
        self.assertEqual(answer.csv_row(1), ["L21_V001", "101", "251", "401"])
        self.assertEqual(answer.dres(1), {"text": "TR-L21_V001-101,251,401"})
        self.assertEqual(TrakeAnswer("V", (7, 7)).csv_row(0), ["V", "7", "7"])  # the same frame twice is allowed

    def test_what_cannot_be_sent_is_refused(self):
        for build, message in (
                (lambda: QaAnswer("V", 1, 1, "  "), "needs an answer"),
                (lambda: TrakeAnswer("V", (5,)), "two or more frames in time order"),
                (lambda: TrakeAnswer("V", (9, 4)), "two or more frames in time order"),
                (lambda: KisAnswer("", 1, 1), "needs a video id"),
                (lambda: KisAnswer("V", -1, 1), "cannot be negative"),
                (lambda: TrakeAnswer("V", (-3, 4)), "cannot be negative")):
            with self.assertRaisesRegex(ValueError, message):
                build()
        with self.assertRaisesRegex(ValueError, "cannot contain '-'"):
            QaAnswer("V", 1, 1, "Bà Rịa-Vũng Tàu").dres(0)
        self.assertEqual(QaAnswer("V", 1, 1, "Bà Rịa-Vũng Tàu").csv_row(0)[2], "Bà Rịa-Vũng Tàu")  # fine in the file


class WriteCsvTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "answers" / "query.csv"

    def test_no_header_unix_line_ends_and_the_accents_kept(self):
        write_csv(self.path, [QaAnswer("L01_V002", 10, 400, "Hà Nội, Việt Nam"), KisAnswer("L01_V003", 20, 800)], 1)
        raw = self.path.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertEqual(raw.decode("utf-8"), 'L01_V002,11,"Hà Nội, Việt Nam"\nL01_V003,21\n')
        with self.path.open(encoding="utf-8", newline="") as handle:
            self.assertEqual(list(csv.reader(handle))[0][2], "Hà Nội, Việt Nam")

    def test_at_most_a_hundred_rows_and_the_old_file_survives_a_refusal(self):
        write_csv(self.path, [KisAnswer("V", 1, 40)], 0)
        with self.assertRaisesRegex(ValueError, "101 rows; the organisers accept at most 100"):
            write_csv(self.path, [KisAnswer("V", n, n * 40) for n in range(101)], 0)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "V,1\n")
        write_csv(self.path, [KisAnswer("V", n, n * 40) for n in range(100)], 0)
        self.assertEqual(len(self.path.read_text(encoding="utf-8").splitlines()), 100)

    def test_a_failed_write_leaves_no_temporary_file(self):
        class Broken:
            video_id = "V"

            def csv_row(self, frame_id_base):
                raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            write_csv(self.path, [Broken()], 0)
        self.assertEqual(list(self.path.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
