"""Clipboard and primary-selection access across Wayland and X11."""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
from typing import Mapping


@dataclass(frozen=True)
class ClipboardBackend:
    name: str
    display_server: str
    read_primary: tuple[str, ...]
    read_clipboard: tuple[str, ...]
    write_primary: tuple[str, ...]
    clear_primary: tuple[str, ...]


WAYLAND = ClipboardBackend(
    "wl-clipboard",
    "wayland",
    ("wl-paste", "--no-newline", "--primary"),
    ("wl-paste", "--no-newline"),
    ("wl-copy", "--primary"),
    ("wl-copy", "--primary", "--clear"),
)
XCLIP = ClipboardBackend(
    "xclip",
    "x11",
    ("xclip", "-selection", "primary", "-out"),
    ("xclip", "-selection", "clipboard", "-out"),
    ("xclip", "-selection", "primary", "-in"),
    ("xclip", "-selection", "primary", "-in"),
)
XSEL = ClipboardBackend(
    "xsel",
    "x11",
    ("xsel", "--primary", "--output"),
    ("xsel", "--clipboard", "--output"),
    ("xsel", "--primary", "--input"),
    ("xsel", "--primary", "--clear"),
)


def display_server(environ: Mapping[str, str] | None = None) -> str:
    environment = os.environ if environ is None else environ
    session = environment.get("XDG_SESSION_TYPE", "").strip().lower()
    if session in {"wayland", "x11"}:
        return session
    if environment.get("WAYLAND_DISPLAY", "").strip():
        return "wayland"
    if environment.get("DISPLAY", "").strip():
        return "x11"
    return "unknown"


def available_backends(
    environ: Mapping[str, str] | None = None,
    *,
    which=shutil.which,
) -> list[ClipboardBackend]:
    server = display_server(environ)
    ordered = (WAYLAND, XCLIP, XSEL) if server != "x11" else (XCLIP, XSEL, WAYLAND)
    return [
        backend
        for backend in ordered
        if which(backend.read_primary[0]) and which(backend.write_primary[0])
    ]


def preferred_backend(
    environ: Mapping[str, str] | None = None,
    *,
    which=shutil.which,
) -> ClipboardBackend | None:
    backends = available_backends(environ, which=which)
    server = display_server(environ)
    return next(
        (backend for backend in backends if backend.display_server == server),
        backends[0] if backends else None,
    )


def _run(
    args: tuple[str, ...], *, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=2,
        check=False,
    )


def read_selection(primary: bool = True) -> str:
    for backend in available_backends():
        args = backend.read_primary if primary else backend.read_clipboard
        try:
            completed = _run(args)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if completed.returncode == 0:
            text = completed.stdout.replace("\x00", "").strip()
            if text:
                return text
    return ""


def write_primary(text: str) -> bool:
    backend = preferred_backend()
    if backend is None:
        return False
    try:
        completed = _run(backend.write_primary, input_text=text)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def clear_primary_if_owned(expected: str) -> bool:
    current = read_selection(primary=True)
    if current != expected.strip():
        return False
    backend = preferred_backend()
    if backend is None:
        return False
    input_text = "" if backend is XCLIP else None
    try:
        completed = _run(backend.clear_primary, input_text=input_text)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
