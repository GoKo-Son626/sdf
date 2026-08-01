"""Configurable Markdown vocabulary storage."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any


SAVE_MODES = ("off", "all", "terms", "texts")


@dataclass(frozen=True)
class ArchiveOutcome:
    status: str
    path: Path | None = None

    @property
    def saved(self) -> bool:
        return self.status == "saved"


def vocabulary_path(config: dict[str, str]) -> Path | None:
    raw = config.get("VOCABULARY_FILE", "").strip()
    if not raw:
        return None
    expanded = os.path.expandvars(os.path.expanduser(raw))
    return Path(expanded).resolve()


def save_mode(config: dict[str, str]) -> str:
    mode = config.get("SAVE_MODE", "off").strip().lower()
    return mode if mode in SAVE_MODES else "off"


def should_save(kind: str, mode: str) -> bool:
    return mode == "all" or (mode == "terms" and kind == "term") or (
        mode == "texts" and kind == "text"
    )


def markdown_text(value: Any) -> str:
    text = str(value or "").strip()
    return text.replace("\r", "").replace("\n", "<br>")


def ensure_vocabulary_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(
        "# Translation Vocabulary\n\n"
        "> One source line and one translation line, recorded by `sdf` according to your save policy.\n\n",
        encoding="utf-8",
    )


def archive_result(result: dict[str, Any], config: dict[str, str]) -> ArchiveOutcome:
    mode = save_mode(config)
    if mode == "off":
        return ArchiveOutcome("disabled")

    path = vocabulary_path(config)
    if path is None:
        return ArchiveOutcome("path_missing")

    kind = str(result.get("kind", "text"))
    if not should_save(kind, mode):
        return ArchiveOutcome("filtered", path)

    ensure_vocabulary_file(path)
    query = re.sub(r"\s+", " ", str(result.get("query", ""))).strip()
    existing = path.read_text(encoding="utf-8")
    query_key = markdown_text(query).casefold()
    already_saved = any(
        line.rstrip().startswith("**")
        and line.rstrip().endswith("**")
        and line.rstrip()[2:-2].casefold() == query_key
        for line in existing.splitlines()
    )
    if already_saved:
        return ArchiveOutcome("duplicate", path)

    translation = "; ".join(str(item) for item in result.get("translations", []))
    lines = [
        f"**{markdown_text(query)}**  ",
        markdown_text(translation),
        "",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return ArchiveOutcome("saved", path)
