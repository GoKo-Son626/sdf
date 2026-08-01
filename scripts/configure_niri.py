#!/usr/bin/env python3
"""在 niri 配置中安装或更新 SDF 全局快捷键。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


BIND_PATTERN = re.compile(r"^\s*(?:Mod|Super)\+Shift\+T\b.*$", re.MULTILINE)


def configure(config_file: Path, command: str) -> str:
    if not config_file.exists():
        raise RuntimeError(f"找不到 niri 配置：{config_file}")

    text = config_file.read_text(encoding="utf-8")
    binding = (
        "    Mod+Shift+T repeat=false allow-inhibiting=false "
        'hotkey-overlay-title="翻译选中文字" '
        f'{{ spawn "{command}"; }}'
    )

    if BIND_PATTERN.search(text):
        updated = BIND_PATTERN.sub(binding, text, count=1)
        action = "已更新"
    else:
        marker = re.search(r"^binds\s*\{\s*$", text, re.MULTILINE)
        if not marker:
            raise RuntimeError("niri 配置中没有找到 binds { 区块")
        insert_at = marker.end()
        updated = text[:insert_at] + "\n" + binding + text[insert_at:]
        action = "已安装"

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
        print(f"niri 快捷键配置失败：{exc}")
        return 1
    print(f"niri 快捷键{action}：Super+Shift+T → {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
