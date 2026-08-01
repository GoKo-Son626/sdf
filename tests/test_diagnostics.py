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
            "PROVIDER_NAME": "DeepSeek（深度求索）",
            "MODEL": "deepseek-v4-flash",
            "API_KEY": "绝不能输出的测试密钥",
            "SAVE_MODE": "off",
        }
        with (
            patch.object(diagnostics, "config_file", return_value=Path("/不存在")),
            patch("sys.stdout", new_callable=io.StringIO) as output,
            patch.object(diagnostics.shutil, "which", return_value="/usr/bin/工具"),
        ):
            diagnostics.print_diagnostics(config)
        self.assertNotIn(config["API_KEY"], output.getvalue())
        self.assertIn("DeepSeek（深度求索）", output.getvalue())

    def test_missing_desktop_commands_are_errors(self) -> None:
        items = diagnostics.collect_diagnostics(
            {"SAVE_MODE": "off"},
            environ={},
            which=lambda command: None,
        )
        missing = [item for item in items if item.level == "error"]
        self.assertEqual(
            {item.label for item in missing},
            {"wl-copy", "wl-paste", "zenity", "notify-send"},
        )

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
        config_item = next(item for item in items if item.label == "配置文件")
        self.assertEqual(config_item.level, "ok")
        self.assertIn("600", config_item.detail)


if __name__ == "__main__":
    unittest.main()
