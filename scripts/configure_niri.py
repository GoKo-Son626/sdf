#!/usr/bin/env python3
"""Install or update the SDF global shortcut in a niri config."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sdf_translate.hotkeys import DEFAULT_SHORTCUT, configure_niri


def configure(config_file: Path, command: str, shortcut: str = DEFAULT_SHORTCUT) -> str:
    return configure_niri(config_file, command, shortcut)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--shortcut", default=DEFAULT_SHORTCUT)
    args = parser.parse_args()
    try:
        action = configure(args.config.expanduser(), args.command, args.shortcut)
    except RuntimeError as exc:
        print(f"Failed to configure the niri shortcut: {exc}")
        return 1
    print(f"niri shortcut {action}: {args.shortcut} -> {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
