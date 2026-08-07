"""Configure the global translation shortcut on supported desktops."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Mapping


DEFAULT_SHORTCUT = "Super+Shift+T"


def desktop_name(environ: Mapping[str, str] | None = None) -> str:
    environment = os.environ if environ is None else environ
    value = ":".join(
        environment.get(key, "")
        for key in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION")
    ).lower()
    if "xfce" in value:
        return "xfce"
    if "niri" in value or environment.get("NIRI_SOCKET"):
        return "niri"
    if "gnome" in value:
        return "gnome"
    if "kde" in value or "plasma" in value:
        return "kde"
    return "unknown"


def normalize_shortcut(shortcut: str) -> str:
    aliases = {
        "ctrl": "Ctrl",
        "control": "Ctrl",
        "alt": "Alt",
        "shift": "Shift",
        "super": "Super",
        "mod": "Super",
    }
    parts = [part.strip() for part in shortcut.split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError("a shortcut needs at least one modifier and one key")
    normalized = [
        aliases.get(part.lower(), part.upper() if len(part) == 1 else part)
        for part in parts
    ]
    if normalized[-1] in {"Ctrl", "Alt", "Shift", "Super"}:
        raise ValueError("the final shortcut component must be a key")
    return "+".join(normalized)


def xfce_accelerator(shortcut: str) -> str:
    parts = normalize_shortcut(shortcut).split("+")
    modifiers = "".join(f"<{part}>" for part in parts[:-1])
    return modifiers + parts[-1].lower()


def niri_shortcut(shortcut: str) -> str:
    parts = normalize_shortcut(shortcut).split("+")
    return "+".join("Mod" if part == "Super" else part for part in parts)


def configure_niri(config_file: Path, command: str, shortcut: str) -> str:
    if not config_file.exists():
        raise RuntimeError(f"niri configuration not found: {config_file}")
    text = config_file.read_text(encoding="utf-8")
    key = niri_shortcut(shortcut)
    binding = (
        f"    {key} repeat=false allow-inhibiting=false "
        'hotkey-overlay-title="Translate Selected Text" '
        f'{{ spawn "{command}"; }}'
    )
    existing = re.compile(
        r'^\s*[^\n{]+\{\s*spawn\s+"[^"]*sdf-global";\s*\}\s*$',
        re.MULTILINE,
    )
    if existing.search(text):
        updated = existing.sub(binding, text, count=1)
        action = "updated"
    else:
        marker = re.search(r"^binds\s*\{\s*$", text, re.MULTILINE)
        if not marker:
            raise RuntimeError("no binds { block was found in the niri configuration")
        updated = text[: marker.end()] + "\n" + binding + text[marker.end() :]
        action = "installed"
    if updated != text:
        config_file.write_text(updated, encoding="utf-8")
    return action


def _xfconf(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["xfconf-query", "-c", "xfce4-keyboard-shortcuts", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def configure_xfce(command: str, shortcut: str, *, force: bool = False) -> str:
    if not shutil.which("xfconf-query"):
        raise RuntimeError("xfconf-query is missing; install the xfconf package")
    property_name = f"/commands/custom/{xfce_accelerator(shortcut)}"
    current = _xfconf(["-p", property_name])
    existing = current.stdout.strip() if current.returncode == 0 else ""
    if existing and existing != command and not force:
        raise RuntimeError(
            f"{normalize_shortcut(shortcut)} is already assigned to: {existing}. "
            "Run the command again with --force to replace it."
        )
    args = ["-p", property_name, "-s", command]
    if current.returncode != 0:
        args[2:2] = ["-n", "-t", "string"]
    updated = _xfconf(args)
    if updated.returncode != 0:
        detail = updated.stderr.strip() or "xfconf rejected the shortcut"
        raise RuntimeError(detail)
    return "updated" if existing else "installed"


def remove_xfce_shortcut(command: str, shortcut: str) -> bool:
    property_name = f"/commands/custom/{xfce_accelerator(shortcut)}"
    current = _xfconf(["-p", property_name])
    if current.returncode != 0 or current.stdout.strip() != command:
        return False
    removed = _xfconf(["-p", property_name, "-r"])
    return removed.returncode == 0


def configure_shortcut(
    command: str,
    shortcut: str = DEFAULT_SHORTCUT,
    *,
    force: bool = False,
    previous_shortcut: str = "",
    environ: Mapping[str, str] | None = None,
    config_home: Path | None = None,
) -> tuple[str, str]:
    shortcut = normalize_shortcut(shortcut)
    desktop = desktop_name(environ)
    home = config_home or Path(
        os.environ.get("XDG_CONFIG_HOME", "~/.config")
    ).expanduser()
    if desktop == "xfce":
        action = configure_xfce(command, shortcut, force=force)
        if previous_shortcut and normalize_shortcut(previous_shortcut) != shortcut:
            remove_xfce_shortcut(command, previous_shortcut)
        return desktop, action
    if desktop == "niri" or (home / "niri/config.kdl").exists():
        return "niri", configure_niri(home / "niri/config.kdl", command, shortcut)
    raise RuntimeError(manual_shortcut_help(command, desktop))


def manual_shortcut_help(command: str, desktop: str | None = None) -> str:
    name = desktop or desktop_name()
    if name in {"niri", "xfce"}:
        return (
            f"Automatic shortcut setup is supported for {name}. Run sdf --hotkey "
            f"to bind {command} to {DEFAULT_SHORTCUT}, or pass another shortcut."
        )
    return (
        f"Automatic shortcut setup is not available for {name}. "
        f"Open the desktop keyboard shortcut settings and bind {command} "
        f"to {DEFAULT_SHORTCUT}."
    )
