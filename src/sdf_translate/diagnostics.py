"""Safely inspect the runtime environment, desktop dependencies, and configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import stat
from typing import Callable, Mapping

from . import __version__
from .paths import config_file
from .storage import save_mode, vocabulary_path


@dataclass(frozen=True)
class DiagnosticItem:
    """One diagnostic result that contains no sensitive values."""

    label: str
    detail: str
    level: str = "ok"


def collect_diagnostics(
    config: dict[str, str],
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> list[DiagnosticItem]:
    """Collect diagnostics without network requests or secret disclosure."""
    environment = os.environ if environ is None else environ
    find_command = shutil.which if which is None else which
    items = [
        DiagnosticItem("Version", f"SDF Translator {__version__}"),
        DiagnosticItem(
            "Python",
            f"{platform.python_version()} / {platform.system()} {platform.machine()}",
        ),
    ]

    wayland = environment.get("WAYLAND_DISPLAY", "").strip()
    if wayland:
        items.append(DiagnosticItem("Display session", f"Wayland ({wayland})"))
    else:
        items.append(
            DiagnosticItem(
                "Display session",
                "Wayland was not detected; terminal translation works, but global selection does not",
                "warning",
            )
        )

    for command, purpose in (
        ("wl-copy", "write the Wayland selection"),
        ("wl-paste", "read the Wayland selection"),
        ("zenity", "show long translation results"),
        ("notify-send", "show term results and errors"),
    ):
        resolved = find_command(command)
        items.append(
            DiagnosticItem(
                command,
                f"Installed: {resolved}" if resolved else f"Missing: required to {purpose}",
                "ok" if resolved else "error",
            )
        )

    path = config_file()
    if path.exists():
        permissions = stat.S_IMODE(path.stat().st_mode)
        private = permissions & 0o077 == 0
        items.append(
            DiagnosticItem(
                "Configuration",
                f"{path} (mode {permissions:03o})",
                "ok" if private else "error",
            )
        )
    else:
        items.append(
            DiagnosticItem("Configuration", f"Not created: {path}", "warning")
        )

    provider = config.get("PROVIDER_NAME", "").strip()
    model = config.get("MODEL", "").strip()
    has_key = bool(config.get("API_KEY", "").strip())
    if provider and has_key:
        items.append(
            DiagnosticItem(
                "AI provider", f"{provider} / {model or 'model not specified'}"
            )
        )
    elif provider in ("Keyless fallback",) or config.get("PROVIDER") == "none":
        items.append(DiagnosticItem("AI provider", "Keyless fallback only"))
    else:
        items.append(
            DiagnosticItem(
                "AI provider",
                "Incomplete configuration; keyless fallback will be used",
                "warning",
            )
        )

    mode = save_mode(config)
    vocabulary = vocabulary_path(config)
    if mode == "off":
        items.append(DiagnosticItem("Vocabulary", "Saving is disabled"))
    elif vocabulary is None:
        items.append(
            DiagnosticItem(
                "Vocabulary",
                f"Save mode is {mode}, but no path is set",
                "warning",
            )
        )
    else:
        items.append(DiagnosticItem("Vocabulary", f"{mode} -> {vocabulary}"))
    return items


def print_diagnostics(config: dict[str, str]) -> int:
    """Print diagnostics and fail when required desktop commands are missing."""
    print("SDF Environment Diagnostics")
    print("=" * 40)
    items = collect_diagnostics(config)
    symbols = {"ok": "✓", "warning": "!", "error": "✗"}
    for item in items:
        print(f"{symbols[item.level]} {item.label}: {item.detail}")
    print()
    print("Diagnostics make no network requests and never read or display API key values.")
    return 1 if any(item.level == "error" for item in items) else 0
