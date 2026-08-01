#!/usr/bin/env python3
"""Reject personal runtime files, credentials, and home paths from Git."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = {"config.env", ".history", "vocabulary.md"}
HOME_PREFIX = "/" + "home/"
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "Google API key": re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    "Bearer token": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    "personal home path": re.compile(
        re.escape(HOME_PREFIX)
        + r"(?!your-name(?:/|\b)|USER(?:/|\b)|<)[^/\s`]+/"
    ),
    "non-placeholder API key": re.compile(
        r"(?m)^API_KEY=(?!$|你的_|在这里填写_|<)[^\s#]+"
    ),
}


def tracked_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [ROOT / item.decode() for item in completed.stdout.split(b"\0") if item]


def main() -> int:
    violations: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT)
        if relative.name in PRIVATE_NAMES or "learn" in relative.parts:
            violations.append(f"private runtime path is tracked: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                violations.append(f"{label} detected in: {relative}")

    if violations:
        print("Repository privacy check failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("Repository privacy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
