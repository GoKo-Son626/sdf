import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sdf_translate import desktop


class DesktopUiTests(unittest.TestCase):
    def test_result_content_only_adds_model_metadata(self) -> None:
        content = desktop.translation_content("original", "translation", "test-model")
        self.assertEqual(
            content,
            "Original\noriginal\n\nTranslation\ntranslation\n\nModel: test-model",
        )
        self.assertNotIn("Archive", content)
        self.assertNotIn("Source", content)

    def test_term_success_uses_one_compact_notification(self) -> None:
        payload = {
            "ok": True,
            "query": "modal",
            "translation": "modal; mode; form",
            "source": "test",
            "kind": "term",
            "saved": False,
            "vocabulary_file": "/tmp/vocabulary.md",
            "warnings": [],
        }
        with (
            patch.object(desktop, "notify") as notify,
            patch.object(desktop, "show_translation_result") as show,
        ):
            desktop.show_result(payload)
        notify.assert_called_once_with(
            "modal",
            "modal; mode; form\n\nModel: test",
            timeout_ms=12000,
        )
        show.assert_not_called()

    def test_text_success_uses_one_result_window(self) -> None:
        payload = {
            "ok": True,
            "query": "This is a sentence.",
            "translation": "This is a translated sentence.",
            "source": "test-model",
            "kind": "text",
            "warnings": [],
        }
        with (
            patch.object(desktop, "notify") as notify,
            patch.object(desktop, "show_translation_result") as show,
        ):
            desktop.show_result(payload)
        notify.assert_not_called()
        show.assert_called_once_with(
            "This is a sentence.", "This is a translated sentence.", "test-model"
        )

    def test_failure_uses_notification_and_no_result_window(self) -> None:
        payload = {"ok": False, "error": "Network connection failed", "warnings": []}
        with (
            patch.object(desktop, "notify") as notify,
            patch.object(desktop, "show_translation_result") as show,
            patch.object(desktop, "show_term_result") as show_term,
        ):
            desktop.show_result(payload)
        notify.assert_called_once()
        show.assert_not_called()
        show_term.assert_not_called()


if __name__ == "__main__":
    unittest.main()
