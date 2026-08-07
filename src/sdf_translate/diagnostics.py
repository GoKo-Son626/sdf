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
from .clipboard import display_server, preferred_backend
from .hotkeys import desktop_name
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

    server = display_server(environment)
    if server in {"wayland", "x11"}:
        endpoint = environment.get(
            "WAYLAND_DISPLAY" if server == "wayland" else "DISPLAY", ""
        )
        detail = server.title() + (f" ({endpoint})" if endpoint else "")
        items.append(DiagnosticItem("Display session", detail))
    else:
        items.append(
            DiagnosticItem(
                "Display session",
                "Neither Wayland nor X11 was detected; terminal translation still works",
                "warning",
            )
        )

    backend = preferred_backend(environment, which=find_command)
    items.append(
        DiagnosticItem(
            "Clipboard",
            f"{backend.name} ({backend.display_server})"
            if backend
            else "No compatible backend; install wl-clipboard for Wayland or xclip for X11",
            "ok" if backend else "error",
        )
    )

    dialog = next(
        (name for name in ("zenity", "yad", "kdialog") if find_command(name)),
        None,
    )
    items.append(
        DiagnosticItem(
            "Result dialog",
            dialog or "Missing: install zenity, yad, or kdialog",
            "ok" if dialog else "error",
        )
    )
    notifier = find_command("notify-send")
    items.append(
        DiagnosticItem(
            "Notifications",
            f"notify-send ({notifier})"
            if notifier
            else "notify-send is missing; dialogs will be used instead",
            "ok" if notifier else "warning",
        )
    )
    desktop = desktop_name(environment)
    auto = desktop in {"niri", "xfce"}
    items.append(
        DiagnosticItem(
            "Desktop shortcut",
            f"{desktop}: automatic setup is supported"
            if auto
            else f"{desktop}: configure sdf-global in keyboard settings",
            "ok" if auto else "warning",
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
