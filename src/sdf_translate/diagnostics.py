"""安全检查运行环境、桌面依赖和用户配置。"""

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
    """一项不包含敏感值的诊断结果。"""

    label: str
    detail: str
    level: str = "ok"


def collect_diagnostics(
    config: dict[str, str],
    *,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> list[DiagnosticItem]:
    """收集诊断信息，但不执行网络请求，也不显示任何密钥。"""
    environment = os.environ if environ is None else environ
    find_command = shutil.which if which is None else which
    items = [
        DiagnosticItem("版本", f"SDF 翻译工具 {__version__}"),
        DiagnosticItem(
            "Python",
            f"{platform.python_version()} / {platform.system()} {platform.machine()}",
        ),
    ]

    wayland = environment.get("WAYLAND_DISPLAY", "").strip()
    if wayland:
        items.append(DiagnosticItem("图形会话", f"Wayland（{wayland}）"))
    else:
        items.append(
            DiagnosticItem(
                "图形会话",
                "没有检测到 Wayland；终端翻译可用，全局选区功能不可用",
                "warning",
            )
        )

    for command, purpose in (
        ("wl-copy", "写入 Wayland 选区"),
        ("wl-paste", "读取 Wayland 选区"),
        ("zenity", "显示长文本结果窗口"),
        ("notify-send", "显示术语和错误通知"),
    ):
        resolved = find_command(command)
        items.append(
            DiagnosticItem(
                command,
                f"已安装：{resolved}" if resolved else f"缺失：用于{purpose}",
                "ok" if resolved else "error",
            )
        )

    path = config_file()
    if path.exists():
        permissions = stat.S_IMODE(path.stat().st_mode)
        private = permissions & 0o077 == 0
        items.append(
            DiagnosticItem(
                "配置文件",
                f"{path}（权限 {permissions:03o}）",
                "ok" if private else "error",
            )
        )
    else:
        items.append(
            DiagnosticItem("配置文件", f"尚未创建：{path}", "warning")
        )

    provider = config.get("PROVIDER_NAME", "").strip()
    model = config.get("MODEL", "").strip()
    has_key = bool(config.get("API_KEY", "").strip())
    if provider and has_key:
        items.append(DiagnosticItem("大模型", f"{provider} / {model or '未指定模型'}"))
    elif provider in ("免费备用翻译",) or config.get("PROVIDER") == "none":
        items.append(DiagnosticItem("大模型", "已选择仅使用免密备用翻译"))
    else:
        items.append(
            DiagnosticItem(
                "大模型",
                "未完整配置，将使用免密备用翻译",
                "warning",
            )
        )

    mode = save_mode(config)
    vocabulary = vocabulary_path(config)
    if mode == "off":
        items.append(DiagnosticItem("生词本", "保存已关闭"))
    elif vocabulary is None:
        items.append(
            DiagnosticItem("生词本", f"保存模式为 {mode}，但未设置路径", "warning")
        )
    else:
        items.append(DiagnosticItem("生词本", f"{mode} → {vocabulary}"))
    return items


def print_diagnostics(config: dict[str, str]) -> int:
    """打印中文诊断报告；存在缺失桌面依赖时返回非零状态。"""
    print("SDF 环境诊断")
    print("=" * 40)
    items = collect_diagnostics(config)
    symbols = {"ok": "✓", "warning": "!", "error": "✗"}
    for item in items:
        print(f"{symbols[item.level]} {item.label}：{item.detail}")
    print()
    print("诊断不会联网，也不会读取或显示 API 密钥内容。")
    return 1 if any(item.level == "error" for item in items) else 0
