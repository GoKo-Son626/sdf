import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sdf_translate import clipboard


class ClipboardTests(unittest.TestCase):
    def test_detects_x11_from_display(self) -> None:
        self.assertEqual(clipboard.display_server({"DISPLAY": ":0"}), "x11")

    def test_prefers_xclip_on_x11(self) -> None:
        installed = {"xclip", "wl-copy", "wl-paste"}
        backend = clipboard.preferred_backend(
            {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"},
            which=lambda command: f"/usr/bin/{command}" if command in installed else None,
        )
        self.assertIs(backend, clipboard.XCLIP)

    def test_prefers_wayland_backend_on_wayland(self) -> None:
        backend = clipboard.preferred_backend(
            {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-1"},
            which=lambda command: f"/usr/bin/{command}",
        )
        self.assertIs(backend, clipboard.WAYLAND)

    def test_reads_x11_primary_selection(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "selected text\n", "")
        with (
            patch.object(clipboard, "available_backends", return_value=[clipboard.XCLIP]),
            patch.object(clipboard, "_run", return_value=completed) as run,
        ):
            result = clipboard.read_selection(primary=True)
        self.assertEqual(result, "selected text")
        run.assert_called_once_with(("xclip", "-selection", "primary", "-out"))


if __name__ == "__main__":
    unittest.main()
