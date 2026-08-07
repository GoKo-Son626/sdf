import io
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from sdf_translate import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_report_never_contains_api_key(self) -> None:
        config = {
            "PROVIDER": "deepseek",
            "PROVIDER_NAME": "DeepSeek",
            "MODEL": "deepseek-v4-flash",
            "API_KEY": "secret-that-must-never-appear",
            "SAVE_MODE": "off",
        }
        with (
            patch.object(diagnostics, "config_file", return_value=Path("/missing")),
            patch("sys.stdout", new_callable=io.StringIO) as output,
            patch.object(diagnostics.shutil, "which", return_value="/usr/bin/tool"),
        ):
            diagnostics.print_diagnostics(config)
        self.assertNotIn(config["API_KEY"], output.getvalue())
        self.assertIn("DeepSeek", output.getvalue())

    def test_missing_desktop_backends_are_reported(self) -> None:
        items = diagnostics.collect_diagnostics(
            {"SAVE_MODE": "off"},
            environ={},
            which=lambda command: None,
        )
        missing = [item for item in items if item.level == "error"]
        self.assertEqual({item.label for item in missing}, {"Clipboard", "Result dialog"})

    def test_x11_accepts_xclip_without_wayland_tools(self) -> None:
        installed = {"xclip", "zenity", "notify-send", "xfconf-query"}
        items = diagnostics.collect_diagnostics(
            {"SAVE_MODE": "off"},
            environ={"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0", "XDG_CURRENT_DESKTOP": "XFCE"},
            which=lambda command: f"/usr/bin/{command}" if command in installed else None,
        )
        self.assertFalse(any(item.level == "error" for item in items))
        clipboard_item = next(item for item in items if item.label == "Clipboard")
        self.assertIn("xclip", clipboard_item.detail)

    def test_private_config_permissions_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.env"
            path.write_text("SAVE_MODE=off\n", encoding="utf-8")
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            with patch.object(diagnostics, "config_file", return_value=path):
                items = diagnostics.collect_diagnostics(
                    {"SAVE_MODE": "off"},
                    environ={"WAYLAND_DISPLAY": "wayland-1"},
                    which=lambda command: f"/usr/bin/{command}",
                )
        config_item = next(item for item in items if item.label == "Configuration")
        self.assertEqual(config_item.level, "ok")
        self.assertIn("600", config_item.detail)


if __name__ == "__main__":
    unittest.main()
