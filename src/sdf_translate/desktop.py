#!/usr/bin/env python3
"""Translate the current Wayland primary selection from a global hotkey."""

from __future__ import annotations

import fcntl
import os
import subprocess
import tempfile
from pathlib import Path

from .cli import load_config, translate_machine

MAX_INPUT_CHARS = 12000


def run(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def notify(title: str, message: str, urgency: str = "normal") -> None:
    subprocess.Popen(
        [
            "notify-send",
            f"--urgency={urgency}",
            "--app-name=全局翻译",
            title,
            message,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def clipboard_text(*, primary: bool) -> str:
    args = ["wl-paste", "--no-newline"]
    if primary:
        args.append("--primary")
    try:
        completed = run(args, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    text = completed.stdout.replace("\x00", "").strip()
    return text


def preview(text: str, limit: int = 320) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "…"


def confirm_clipboard(text: str) -> bool:
    message = (
        "没有检测到鼠标选中的文字。\n\n"
        "是否翻译普通剪贴板中的以下内容？\n\n"
        f"{preview(text)}"
    )
    try:
        completed = subprocess.run(
            [
                "zenity",
                "--question",
                "--title=全局翻译",
                "--ok-label=翻译",
                "--cancel-label=取消",
                "--width=520",
                f"--text={message}",
            ],
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def select_input() -> tuple[str, str]:
    selected = clipboard_text(primary=True)
    if selected:
        return selected, "鼠标选区"

    copied = clipboard_text(primary=False)
    if not copied:
        return "", ""
    if confirm_clipboard(copied):
        return copied, "剪贴板"
    return "", ""


def translate(text: str) -> dict[str, object]:
    config = load_config()
    if config.get("HTTPS_PROXY"):
        os.environ["HTTPS_PROXY"] = config["HTTPS_PROXY"]
        os.environ["https_proxy"] = config["HTTPS_PROXY"]
    payload, _ = translate_machine(
        text, config.get("TRANSLATION_DOMAIN", ""), config
    )
    return payload


def show_translation_result(
    query: str,
    translation: str,
    source: str,
    *,
    is_term: bool,
    archive_status: str = "",
) -> None:
    content = f"原文\n{query}\n\n翻译\n{translation}"
    if source:
        content += f"\n\n来源：{source}"
    if archive_status:
        content += f"\n归档：{archive_status}"
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="global-translation-",
            suffix=".txt",
            delete=False,
        ) as handle:
            handle.write(content)
            temp_path = handle.name
        subprocess.run(
            [
                "zenity",
                "--text-info",
                "--title=翻译结果",
                f"--width={560 if is_term else 760}",
                f"--height={260 if is_term else 480}",
                "--ok-label=关闭",
                "--font=Sans 12",
                f"--filename={temp_path}",
            ],
            check=False,
        )
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def show_result(payload: dict[str, object]) -> None:
    if not payload.get("ok"):
        warnings = payload.get("warnings") or []
        warning_text = "\n".join(str(item) for item in warnings)
        error = str(payload.get("error") or "翻译失败")
        message = f"{warning_text}\n{error}".strip()
        title = "已阻止翻译" if error.startswith("已阻止翻译：") else "翻译失败"
        notify(title, message, "critical")
        return

    query = str(payload.get("query") or "")
    translation = str(payload.get("translation") or "")
    source = str(payload.get("source") or "")
    warnings = payload.get("warnings") or []
    if warnings:
        notify("翻译备用提示", "\n".join(str(item) for item in warnings))

    vocabulary_file = str(payload.get("vocabulary_file") or "vocabulary.md")
    if payload.get("saved") is True:
        archive_status = f"已保存到 {vocabulary_file}"
    elif payload.get("saved") is False:
        archive_status = "未保存或已有相同记录"
    else:
        archive_status = ""
    show_translation_result(
        query,
        translation,
        source,
        is_term=payload.get("kind") == "term",
        archive_status=archive_status,
    )


def main() -> int:
    lock_path = Path(tempfile.gettempdir()) / f"global-translate-{os.getuid()}.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            notify("正在翻译", "已有一个翻译任务正在运行")
            return 0

        text, input_source = select_input()
        if not text:
            notify(
                "没有检测到文字",
                "请先用鼠标选中英文；扫描版 PDF 需要使用 OCR。",
            )
            return 1
        if len(text) > MAX_INPUT_CHARS:
            notify(
                "选中文字过长",
                f"当前最多支持 {MAX_INPUT_CHARS} 个字符，请缩小选择范围。",
                "critical",
            )
            return 1

        payload = translate(text)
        show_result(payload)
        return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
