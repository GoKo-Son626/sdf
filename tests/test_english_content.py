from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
HAN_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
TEXT_SUFFIXES = {".md", ".py", ".sh", ".vim", ".lua", ".yml", ".toml"}
TEXT_NAMES = {"LICENSE", "PKGBUILD", ".SRCINFO", "config.example"}


class EnglishContentTests(unittest.TestCase):
    def test_tracked_project_content_contains_no_han_characters(self) -> None:
        failures: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.name == "vocabulary.md" or "learn" in path.parts:
                continue
            if path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if HAN_PATTERN.search(content):
                failures.append(str(path.relative_to(ROOT)))
        self.assertEqual(failures, [], f"Han characters found in: {failures}")


if __name__ == "__main__":
    unittest.main()
