"""The files around the code: the video list and its README, the requirements, the licence, .gitignore."""
import ast
import csv
import re
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# module name -> the package that provides it; a new third-party import has to be added here
# and to a requirements file
PACKAGES = {"PIL": "pillow", "yaml": "pyyaml", "cv2": "opencv-python", "av": "av", "numpy": "numpy",
            "torch": "torch", "transformers": "transformers", "pymilvus": "pymilvus", "open_clip": "open_clip_torch",
            "faster_whisper": "faster-whisper", "transnetv2_pytorch": "transnetv2-pytorch", "paddleocr": "paddleocr",
            "ultralytics": "ultralytics"}
REQUIREMENT = re.compile(r"^[A-Za-z0-9_.\[\]-]+(==[\w.]+|[<>]\d+(,[<>]\d+)?)(\s+#.*)?$")


def videos():
    with (ROOT / "data" / "videos.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class VideoListTest(unittest.TestCase):
    def test_every_row_is_well_formed(self):
        rows = videos()
        self.assertEqual(len({row["video_id"] for row in rows}), len(rows))
        for row in rows:
            self.assertRegex(row["video_id"], r"^L\d\d_V\d{3}$")
            self.assertEqual(row["url"], f"https://www.youtube.com/watch?v={row['youtube_id']}")
            self.assertGreater(float(Fraction(row["fps"])), 0)
            for column in ("length_s", "frames", "width", "height"):
                self.assertGreater(int(row[column]), 0, row["video_id"])

    def test_the_readme_describes_this_list(self):
        rows, readme = videos(), (ROOT / "data" / "README.md").read_text(encoding="utf-8")
        for column in rows[0]:
            self.assertIn(f"`{column}`", readme)
        ids = sorted(row["video_id"] for row in rows)
        hours = sum(int(row["length_s"]) for row in rows) / 3600
        frames = sum(int(row["frames"]) for row in rows)
        for line in (f"The {len(rows)} videos", f"| videos | {len(rows)}, groups {ids[0][:3]} to {ids[-1][:3]} |",
                     f"{hours:.1f} hours, {frames:,} frames"):
            self.assertIn(line, readme)
        published = sorted(row["published"] for row in rows)
        self.assertIn(f"{published[0][:4]}", readme)
        self.assertIn(f"{published[-1][:4]}", readme)
        portrait = sum(int(row["height"]) > int(row["width"]) for row in rows)
        self.assertIn(f"{len(rows) - portrait} videos; 720×1280 (portrait): {portrait}", readme)

    def test_the_readme_sample_row_is_a_row_of_the_list(self):
        readme = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
        sample = next(line for line in readme.splitlines() if line.startswith("L21_V001,"))
        text = (ROOT / "data" / "videos.csv").read_text(encoding="utf-8")
        self.assertIn(sample + "\n", text)


class RequirementsTest(unittest.TestCase):
    def requirement_lines(self):
        for path in sorted(ROOT.glob("requirements*.txt")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.lstrip().startswith("#"):
                    yield path.name, line

    def test_every_line_is_a_pinned_package(self):
        lines = list(self.requirement_lines())
        self.assertGreater(len(lines), 10)
        for name, line in lines:
            self.assertRegex(line, REQUIREMENT, f"{name}: {line}")

    def test_every_third_party_import_has_a_package_in_a_requirements_file(self):
        text = "\n".join(path.read_text(encoding="utf-8").lower() for path in ROOT.glob("requirements*.txt"))
        found = set()
        for folder in ("src", "scripts"):
            for path in (ROOT / folder).rglob("*.py"):
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    if isinstance(node, ast.Import):
                        found.update(alias.name.split(".")[0] for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                        found.add(node.module.split(".")[0])
        for module in sorted(found - set(sys.stdlib_module_names) - {"src", "__future__"}):
            self.assertIn(module, PACKAGES, f"{module} is imported but not mapped to a package")
            self.assertIn(PACKAGES[module], text, f"{PACKAGES[module]} is not in any requirements file")

    def test_the_agpl_package_stays_in_its_own_file(self):
        for path in ROOT.glob("requirements*.txt"):
            has = "ultralytics" in "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                                              if not line.lstrip().startswith("#"))
            self.assertEqual(has, path.name == "requirements-objects.txt", path.name)


class LicenceAndIgnoreTest(unittest.TestCase):
    def test_the_licence_is_mit(self):
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("MIT License\n\nCopyright (c) 2026 "))
        for phrase in ("Permission is hereby granted, free of charge", "THE SOFTWARE IS PROVIDED \"AS IS\"",
                       "The above copyright notice and this permission notice shall be included"):
            self.assertIn(phrase, text)

    def test_gitignore_keeps_data_models_and_secrets_out_and_the_code_in(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for wanted in ("/data/*", "!/data/README.md", "!/data/videos.csv", "/runs/", "/submission/", "*.db", "*.pt",
                       "*.mp4", ".env"):
            self.assertIn(wanted, lines)
        # an unanchored `submission/` would also hide the package src/submission/
        for line in lines:
            self.assertNotIn(line, ("submission/", "runs/", "data/", "data", "src", "src/"))


if __name__ == "__main__":
    unittest.main()
