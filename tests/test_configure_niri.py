from pathlib import Path
import tempfile
import unittest

from scripts.configure_niri import configure


class ConfigureNiriTests(unittest.TestCase):
    def test_installs_binding_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.kdl"
            config.write_text("binds {\n    Mod+T { spawn \"kitty\"; }\n}\n")

            self.assertEqual(configure(config, "/tmp/bin/sdf-global"), "已安装")
            self.assertEqual(configure(config, "/tmp/bin/sdf-global"), "已更新")
            text = config.read_text()
            self.assertEqual(text.count("Mod+Shift+T"), 1)
            self.assertIn('spawn "/tmp/bin/sdf-global"', text)

    def test_updates_existing_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.kdl"
            config.write_text(
                'binds {\n    Mod+Shift+T { spawn "/old/sdf-global"; }\n}\n'
            )

            self.assertEqual(configure(config, "/new/sdf-global"), "已更新")
            text = config.read_text()
            self.assertNotIn("/old/sdf-global", text)
            self.assertIn("/new/sdf-global", text)


if __name__ == "__main__":
    unittest.main()
