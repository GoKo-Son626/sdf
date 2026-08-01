import ast
import io
from pathlib import Path
import re
import tokenize
import unittest


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PYTHON = [
    *sorted((ROOT / "src").rglob("*.py")),
    *sorted((ROOT / "scripts").rglob("*.py")),
    ROOT / "en.py",
    ROOT / "global_translate.py",
]
CHINESE = re.compile(r"[\u4e00-\u9fff]")
ENGLISH_WORDS = re.compile(r"[A-Za-z]+(?:[ -]+[A-Za-z]+){2,}")


class ChineseContentTests(unittest.TestCase):
    def test_production_docstrings_use_chinese(self) -> None:
        failures = []
        for path in PRODUCTION_PYTHON:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(
                    node,
                    (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                ):
                    continue
                docstring = ast.get_docstring(node, clean=False)
                if docstring and not CHINESE.search(docstring):
                    failures.append(f"{path.relative_to(ROOT)}:{getattr(node, 'lineno', 1)}")
        self.assertEqual(failures, [], "发现非中文文档字符串")

    def test_production_comments_do_not_use_english_sentences(self) -> None:
        failures = []
        for path in PRODUCTION_PYTHON:
            text = path.read_text(encoding="utf-8")
            tokens = tokenize.generate_tokens(io.StringIO(text).readline)
            for token in tokens:
                if token.type != tokenize.COMMENT:
                    continue
                comment = token.string.removeprefix("#").strip()
                if comment.startswith(("!", "noqa:")):
                    continue
                if ENGLISH_WORDS.search(comment) and not CHINESE.search(comment):
                    failures.append(f"{path.relative_to(ROOT)}:{token.start[0]}")
        self.assertEqual(failures, [], "发现纯英文源码注释")

    def test_workflow_step_names_use_chinese(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        names = re.findall(r"^\s*- name:\s*(.+)$", workflow, flags=re.MULTILINE)
        self.assertTrue(names)
        self.assertTrue(all(CHINESE.search(name) for name in names))

    def test_editor_plugin_comments_use_chinese(self) -> None:
        for relative in (
            "editor/nvim/sdf-selection.lua",
            "editor/vim/sdf-selection.vim",
        ):
            first_comment = (ROOT / relative).read_text(encoding="utf-8").splitlines()[0]
            self.assertRegex(first_comment, CHINESE)

    def test_public_document_prose_uses_chinese(self) -> None:
        failures = []
        for relative in (
            "README.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "packaging/arch/README.md",
        ):
            in_code = False
            for number, raw_line in enumerate(
                (ROOT / relative).read_text(encoding="utf-8").splitlines(), start=1
            ):
                line = raw_line.strip()
                if line.startswith("```"):
                    in_code = not in_code
                    continue
                if in_code or not line or line.startswith(("[", "<", "<!--")):
                    continue
                if ENGLISH_WORDS.search(line) and not CHINESE.search(line):
                    failures.append(f"{relative}:{number}")
        self.assertEqual(failures, [], "发现纯英文公开文档段落")

    def test_shell_prompts_use_chinese(self) -> None:
        failures = []
        for filename in ("install.sh", "uninstall.sh"):
            for number, line in enumerate(
                (ROOT / filename).read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not re.search(r"\b(?:echo|read\s+-r\s+-p)\b", line):
                    continue
                if not CHINESE.search(line):
                    failures.append(f"{filename}:{number}")
        self.assertEqual(failures, [], "发现非中文 Shell 提示")


if __name__ == "__main__":
    unittest.main()
