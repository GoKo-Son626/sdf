from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EditorPluginTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("nvim"), "Neovim is not installed")
    def test_neovim_plugin_loads(self) -> None:
        subprocess.run(
            [
                "nvim",
                "--headless",
                "-u",
                "NONE",
                "+source editor/nvim/sdf-selection.lua",
                "+qa",
            ],
            cwd=ROOT,
            check=True,
            timeout=10,
        )

    @unittest.skipUnless(shutil.which("vim"), "Vim is not installed")
    def test_vim_plugin_loads(self) -> None:
        subprocess.run(
            [
                "vim",
                "-Nu",
                "NONE",
                "-n",
                "-es",
                "+source editor/vim/sdf-selection.vim",
                "+qa",
            ],
            cwd=ROOT,
            check=True,
            timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
