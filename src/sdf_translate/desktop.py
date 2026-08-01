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


def notify(
    title: str,
    message: str,
    urgency: str = "normal",
    *,
    timeout_ms: int | None = None,
) -> None:
    args = [
        "notify-send",
        f"--urgency={urgency}",
        "--app-name=SDF Translator",
    ]
    if timeout_ms is not None:
        args.append(f"--expire-time={timeout_ms}")
    args.extend((title, message))
    subprocess.Popen(
        args,
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
        "No selected text was detected.\n\n"
        "Translate the following regular clipboard content instead?\n\n"
        f"{preview(text)}"
    )
    try:
        completed = subprocess.run(
            [
                "zenity",
                "--question",
                "--title=SDF Translator",
                "--ok-label=Translate",
                "--cancel-label=Cancel",
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
        return selected, "primary selection"

    copied = clipboard_text(primary=False)
    if not copied:
        return "", ""
    if confirm_clipboard(copied):
        return copied, "clipboard"
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


def translation_content(query: str, translation: str, source: str) -> str:
    content = f"Original\n{query}\n\nTranslation\n{translation}"
    if source:
        content += f"\n\nModel: {source}"
    return content


def show_translation_result(
    query: str,
    translation: str,
    source: str,
) -> None:
    content = translation_content(query, translation, source)
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
                "--title=Translation Result",
                "--width=760",
                "--height=480",
                "--ok-label=Close",
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


def show_term_result(query: str, translation: str, source: str) -> None:
    message = translation
    if source:
        message += f"\n\nModel: {source}"
    notify(query or "Translation Result", message, timeout_ms=12000)


def show_result(payload: dict[str, object]) -> None:
    if not payload.get("ok"):
        warnings = payload.get("warnings") or []
        warning_text = "\n".join(str(item) for item in warnings)
        error = str(payload.get("error") or "Translation failed")
        message = f"{warning_text}\n{error}".strip()
        title = "Translation Blocked" if error.startswith("Translation blocked:") else "Translation Failed"
        notify(title, message, "critical")
        return

    query = str(payload.get("query") or "")
    translation = str(payload.get("translation") or "")
    source = str(payload.get("source") or "")
    warnings = payload.get("warnings") or []
    if warnings:
        notify("Fallback Notice", "\n".join(str(item) for item in warnings))

    if payload.get("kind") == "term":
        show_term_result(query, translation, source)
    else:
        show_translation_result(query, translation, source)


def main() -> int:
    lock_path = Path(tempfile.gettempdir()) / f"global-translate-{os.getuid()}.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            notify("Translation in Progress", "Another translation task is already running")
            return 0

        text, _ = select_input()
        if not text:
            notify(
                "No Text Detected",
                "Select text with the mouse first. Scanned PDFs require OCR.",
            )
            return 1
        if len(text) > MAX_INPUT_CHARS:
            notify(
                "Selection Too Long",
                f"The current limit is {MAX_INPUT_CHARS} characters. Select a smaller range.",
                "critical",
            )
            return 1

        payload = translate(text)
        show_result(payload)
        return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
