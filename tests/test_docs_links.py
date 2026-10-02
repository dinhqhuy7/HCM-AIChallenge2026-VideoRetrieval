"""Every link between the documents points at a file that exists and, if it names a heading, one that exists."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOCUMENTS = [ROOT / "README.md", ROOT / "data" / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")


def without_code(text: str) -> str:
    """The text with fenced blocks and inline code taken out: links and headings inside them are examples."""
    text = re.sub(r"^(```|~~~).*?^\1[^\n]*$", "", text, flags=re.S | re.M)
    return re.sub(r"`[^`\n]*`", "", text)


def slug(heading: str) -> str:
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    heading = re.sub(r"`([^`]*)`", r"\1", heading).strip().lower()
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", heading))


def anchors(path: Path) -> set[str]:
    found, seen = set(), {}
    for match in re.finditer(r"^#{1,6}\s+(.*?)\s*#*\s*$", without_code(path.read_text(encoding="utf-8")), re.M):
        name = slug(match.group(1))
        found.add(name if name not in seen else f"{name}-{seen[name]}")
        seen[name] = seen.get(name, 0) + 1
    return found


class DocumentLinksTest(unittest.TestCase):
    def test_every_internal_link_and_heading_exists(self):
        problems = []
        for document in DOCUMENTS:
            for target in LINK.findall(without_code(document.read_text(encoding="utf-8"))):
                if re.match(r"[a-z][a-z0-9+.-]*:", target):  # http:, https:, mailto: ...
                    continue
                name, _, fragment = target.partition("#")
                path = (document.parent / name).resolve() if name else document
                where = f"{document.relative_to(ROOT)} -> {target}"
                if not path.exists():
                    problems.append(f"{where}: no such file")
                elif fragment and path.suffix == ".md" and fragment not in anchors(path):
                    problems.append(f"{where}: no such heading")
        self.assertEqual(problems, [])

    def test_the_checker_sees_what_it_should(self):
        self.assertEqual(slug("The keyframe map"), "the-keyframe-map")
        self.assertEqual(slug("Milvus Lite (the default)"), "milvus-lite-the-default")
        self.assertEqual(slug("Does the language of the query matter?"), "does-the-language-of-the-query-matter")
        self.assertEqual(slug("`ocr` options"), "ocr-options")
        self.assertIn("what-the-100-rows-are-and-are-not", anchors(ROOT / "docs" / "trake.md"))
        self.assertGreater(len(DOCUMENTS), 10)

    def test_every_diagram_block_is_closed(self):
        for document in DOCUMENTS:
            self.assertEqual(len(re.findall(r"^```", document.read_text(encoding="utf-8"), re.M)) % 2, 0, document)


if __name__ == "__main__":
    unittest.main()
