from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
ARCH_DIR = ROOT / "packaging" / "arch"


class ArchPackagingTests(unittest.TestCase):
    def test_pkgbuild_is_a_vcs_package_template(self) -> None:
        text = (ARCH_DIR / "PKGBUILD").read_text(encoding="utf-8")
        self.assertIn("pkgname=sdf-translator-git", text)
        self.assertIn('source=("sdf-translator::git+$url.git")', text)
        self.assertIn("pkgver()", text)
        self.assertIn("sha256sums=(SKIP)", text)
        self.assertIn("license=(MIT)", text)

    @unittest.skipUnless(shutil.which("makepkg"), "未安装 makepkg")
    def test_srcinfo_matches_pkgbuild(self) -> None:
        generated = subprocess.run(
            ["makepkg", "--printsrcinfo"],
            cwd=ARCH_DIR,
            text=True,
            stdout=subprocess.PIPE,
            check=True,
            timeout=20,
        ).stdout
        committed = (ARCH_DIR / ".SRCINFO").read_text(encoding="utf-8")
        self.assertEqual(generated, committed)


if __name__ == "__main__":
    unittest.main()
