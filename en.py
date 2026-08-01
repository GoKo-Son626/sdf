#!/usr/bin/env python3
"""Backward-compatible development entry point for the sdf command."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sdf_translate.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
