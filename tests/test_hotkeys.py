import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sdf_translate import hotkeys


class HotkeyTests(unittest.TestCase):
    def test_xfce_accelerator(self) -> None:
        self.assertEqual(hotkeys.xfce_accelerator("Super+Shift+T"), "<Super><Shift>t")

    def test_niri_shortcut_can_be_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.kdl"
            path.write_text("binds {\n}\n", encoding="utf-8")
            action = hotkeys.configure_niri(path, "/usr/bin/sdf-global", "Ctrl+Alt+G")
            content = path.read_text(encoding="utf-8")
        self.assertEqual(action, "installed")
        self.assertIn("Ctrl+Alt+G", content)
        self.assertIn('spawn "/usr/bin/sdf-global"', content)

    def test_xfce_refuses_to_overwrite_conflict(self) -> None:
        existing = subprocess.CompletedProcess([], 0, "/usr/bin/other\n", "")
        with (
            patch.object(hotkeys.shutil, "which", return_value="/usr/bin/xfconf-query"),
            patch.object(hotkeys, "_xfconf", return_value=existing),
        ):
            with self.assertRaisesRegex(RuntimeError, "already assigned"):
                hotkeys.configure_xfce("/usr/bin/sdf-global", "Super+Shift+T")

    def test_xfce_creates_custom_command(self) -> None:
        missing = subprocess.CompletedProcess([], 1, "", "not found")
        success = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(hotkeys.shutil, "which", return_value="/usr/bin/xfconf-query"),
            patch.object(hotkeys, "_xfconf", side_effect=[missing, success]) as query,
        ):
            action = hotkeys.configure_xfce("/usr/bin/sdf-global", "Super+Shift+T")
        self.assertEqual(action, "installed")
        self.assertIn("/commands/custom/<Super><Shift>t", query.call_args_list[1].args[0])

    def test_changing_xfce_shortcut_removes_only_owned_previous_binding(self) -> None:
        installed = subprocess.CompletedProcess([], 0, "", "")
        owned = subprocess.CompletedProcess([], 0, "/usr/bin/sdf-global\n", "")
        removed = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(hotkeys.shutil, "which", return_value="/usr/bin/xfconf-query"),
            patch.object(hotkeys, "_xfconf", side_effect=[installed, installed, owned, removed]) as query,
        ):
            hotkeys.configure_shortcut(
                "/usr/bin/sdf-global",
                "Ctrl+Alt+G",
                previous_shortcut="Super+Shift+T",
                environ={"XDG_CURRENT_DESKTOP": "XFCE"},
            )
        self.assertEqual(query.call_args_list[-1].args[0][-1], "-r")


if __name__ == "__main__":
    unittest.main()
