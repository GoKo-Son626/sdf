#!/usr/bin/env python3
"""兼容旧用法的桌面翻译开发入口。"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sdf_translate.desktop import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
