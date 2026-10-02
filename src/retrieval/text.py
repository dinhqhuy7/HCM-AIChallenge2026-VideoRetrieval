"""Text as the keyword lanes compare it: lower case, no Vietnamese marks, digits kept."""
from __future__ import annotations

import re
import unicodedata

_WORD = re.compile(r"\w+")
_SPACES = re.compile(r"\s+")


def fold(text: str) -> str:
    """Lower case without Vietnamese marks: "Bến Thành" becomes "ben thanh".

    Marks are removed on both sides of a match because the OCR model used here cannot
    write most of them: the dictionary of PP-OCRv6_medium_rec holds 23 of the 67 accented
    Vietnamese lower-case letters. A query typed with marks would otherwise never meet the
    text the model read.
    """
    text = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def tokens(text: str) -> list[str]:
    """Words and numbers of ``text``, folded.

    Digits stay. A licence plate, a date or a price is often the one detail that names a
    single frame, and it is made of exactly the characters a "clean the text" step removes:
    "79H-6072" becomes ["79h", "6072"].
    """
    return _WORD.findall(fold(text))


def tidy(text: str) -> str:
    """NFC and single spaces: one spelling for text that looks the same on screen."""
    return _SPACES.sub(" ", unicodedata.normalize("NFC", text)).strip()
