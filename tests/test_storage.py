from pathlib import Path
import tempfile
import unittest

from sdf_translate.storage import archive_result


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.term = {
            "query": "modal",
            "kind": "term",
            "translations": ["模态", "模式", "形式"],
        }
        self.text = {
            "query": "This is a sentence.",
            "kind": "text",
            "translations": ["这是一个句子。"],
        }

    def test_default_is_disabled_and_creates_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vocabulary.md"
            outcome = archive_result(self.term, {"VOCABULARY_FILE": str(path)})
            self.assertEqual(outcome.status, "disabled")
            self.assertFalse(path.exists())

    def test_terms_mode_filters_long_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vocabulary.md"
            config = {"SAVE_MODE": "terms", "VOCABULARY_FILE": str(path)}
            self.assertEqual(archive_result(self.text, config).status, "filtered")
            self.assertFalse(path.exists())
            self.assertEqual(archive_result(self.term, config).status, "saved")
            self.assertIn("modal", path.read_text(encoding="utf-8"))

    def test_texts_mode_and_duplicate_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "vocabulary.md"
            config = {"SAVE_MODE": "texts", "VOCABULARY_FILE": str(path)}
            self.assertEqual(archive_result(self.text, config).status, "saved")
            self.assertEqual(archive_result(self.text, config).status, "duplicate")
            self.assertEqual(archive_result(self.term, config).status, "filtered")


if __name__ == "__main__":
    unittest.main()
