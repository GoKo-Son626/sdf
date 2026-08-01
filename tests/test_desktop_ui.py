import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sdf_translate import desktop


class DesktopUiTests(unittest.TestCase):
    def test_result_content_only_adds_model_metadata(self) -> None:
        content = desktop.translation_content("original", "译文", "test-model")
        self.assertEqual(
            content,
            "原文\noriginal\n\n翻译\n译文\n\n模型：test-model",
        )
        self.assertNotIn("归档", content)
        self.assertNotIn("来源", content)

    def test_term_success_uses_one_compact_notification(self) -> None:
        payload = {
            "ok": True,
            "query": "modal",
            "translation": "模态；模式；形式",
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
            "模态；模式；形式\n\n模型：test",
            timeout_ms=12000,
        )
        show.assert_not_called()

    def test_text_success_uses_one_result_window(self) -> None:
        payload = {
            "ok": True,
            "query": "This is a sentence.",
            "translation": "这是一个句子。",
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
            "This is a sentence.", "这是一个句子。", "test-model"
        )

    def test_failure_uses_notification_and_no_result_window(self) -> None:
        payload = {"ok": False, "error": "网络连接失败", "warnings": []}
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
