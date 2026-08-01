import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sdf_translate import desktop


class DesktopUiTests(unittest.TestCase):
    def test_success_uses_one_result_window_and_no_notification(self) -> None:
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
        notify.assert_not_called()
        show.assert_called_once()

    def test_failure_uses_notification_and_no_result_window(self) -> None:
        payload = {"ok": False, "error": "网络连接失败", "warnings": []}
        with (
            patch.object(desktop, "notify") as notify,
            patch.object(desktop, "show_translation_result") as show,
        ):
            desktop.show_result(payload)
        notify.assert_called_once()
        show.assert_not_called()


if __name__ == "__main__":
    unittest.main()
