#!/usr/bin/env python3
"""阻止个人运行文件、凭据和用户目录路径进入 Git。"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = {"config.env", ".history", "vocabulary.md"}
HOME_PREFIX = "/" + "home/"
PATTERNS = {
    "私钥": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI 格式密钥": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "谷歌 API 密钥": re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"),
    "Bearer 令牌": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    "个人用户目录路径": re.compile(
        re.escape(HOME_PREFIX)
        + r"(?!your-name(?:/|\b)|USER(?:/|\b)|<)[^/\s`]+/"
    ),
    "非占位 API 密钥": re.compile(
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
            violations.append(f"个人运行文件已被跟踪：{relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                violations.append(f"{label} detected in: {relative}")

    if violations:
        print("仓库隐私检查失败：")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("仓库隐私检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
