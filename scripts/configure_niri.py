#!/usr/bin/env python3
"""Install or update the SDF global shortcut in a niri config."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


BIND_PATTERN = re.compile(r"^\s*(?:Mod|Super)\+Shift\+T\b.*$", re.MULTILINE)


def configure(config_file: Path, command: str) -> str:
    if not config_file.exists():
        raise RuntimeError(f"niri configuration not found: {config_file}")

    text = config_file.read_text(encoding="utf-8")
    binding = (
        "    Mod+Shift+T repeat=false allow-inhibiting=false "
        'hotkey-overlay-title="Translate Selected Text" '
        f'{{ spawn "{command}"; }}'
    )

    if BIND_PATTERN.search(text):
        updated = BIND_PATTERN.sub(binding, text, count=1)
        action = "updated"
    else:
        marker = re.search(r"^binds\s*\{\s*$", text, re.MULTILINE)
        if not marker:
            raise RuntimeError("no binds { block was found in the niri configuration")
        insert_at = marker.end()
        updated = text[:insert_at] + "\n" + binding + text[insert_at:]
        action = "installed"

    if updated != text:
        config_file.write_text(updated, encoding="utf-8")
    return action


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--command", required=True)
    args = parser.parse_args()
    try:
        action = configure(args.config.expanduser(), args.command)
    except RuntimeError as exc:
        print(f"Failed to configure the niri shortcut: {exc}")
        return 1
    print(f"niri shortcut {action}: Super+Shift+T -> {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
