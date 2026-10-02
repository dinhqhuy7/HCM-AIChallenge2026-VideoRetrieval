import sys
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.text import fold, tidy, tokens  # noqa: E402


class FoldTest(unittest.TestCase):
    def test_marks_and_case(self):
        self.assertEqual(fold("Bến Thành, Đà Nẵng, Hồ Chí Minh"), "ben thanh, da nang, ho chi minh")
        self.assertEqual(fold("ẮẰẲẴẶ ỨỪỬỮỰ ỲỶỸỴÝ Đđ"), "aaaaa uuuuu yyyyy dd")

    def test_composed_and_decomposed_input_agree(self):
        text = "Nghĩa tình đồng bào"
        self.assertEqual(fold(unicodedata.normalize("NFD", text)), fold(unicodedata.normalize("NFC", text)))

    def test_folding_twice_changes_nothing(self):
        once = fold("Việt Nam đi là ghiền")
        self.assertEqual(fold(once), once)


class TokensTest(unittest.TestCase):
    def test_digits_stay(self):
        self.assertEqual(tokens("Biển số 79H-6072!"), ["bien", "so", "79h", "6072"])
        self.assertEqual(tokens("Ngày 12/9/2024"), ["ngay", "12", "9", "2024"])

    def test_query_and_screen_text_meet(self):
        self.assertEqual(tokens("SÀI GÒN BAO DUNG"), tokens("sai gon bao dung"))

    def test_empty(self):
        self.assertEqual(tokens("  --  "), [])


class TidyTest(unittest.TestCase):
    def test_one_spelling(self):
        decomposed = "  tiếng   Việt \n"
        self.assertEqual(tidy(decomposed), "tiếng Việt")
        self.assertEqual(tidy(decomposed), unicodedata.normalize("NFC", "tiếng Việt"))


if __name__ == "__main__":
    unittest.main()
