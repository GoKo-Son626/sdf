"""解析开发模式和安装模式下的用户运行路径。"""

from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "sdf-translator"
PACKAGE_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_DIR.parents[1]


def _xdg_path(env_name: str, fallback: str) -> Path:
    return Path(os.environ.get(env_name, Path.home() / fallback)).expanduser()


def is_source_checkout() -> bool:
    return (SOURCE_ROOT / "pyproject.toml").is_file()


def config_file() -> Path:
    override = os.environ.get("SDF_CONFIG_FILE")
    if override:
        return Path(override).expanduser()
    legacy = SOURCE_ROOT / "config.env"
    if is_source_checkout() and legacy.exists():
        return legacy
    return _xdg_path("XDG_CONFIG_HOME", ".config") / APP_NAME / "config.env"


def history_file() -> Path:
    override = os.environ.get("SDF_HISTORY_FILE")
    if override:
        return Path(override).expanduser()
    legacy = SOURCE_ROOT / ".history"
    if is_source_checkout() and legacy.exists():
        return legacy
    return _xdg_path("XDG_STATE_HOME", ".local/state") / APP_NAME / "history"
