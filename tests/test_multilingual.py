import unittest
from unittest.mock import patch

from sdf_translate import cli


class MultilingualTranslationTests(unittest.TestCase):
    def test_terms_are_detected_across_writing_systems(self) -> None:
        for query in ("virtualization", "condición de carrera", "仮想化", "سباق البيانات"):
            with self.subTest(query=query):
                self.assertTrue(cli.is_short_term(query))

    def test_sentences_are_not_detected_as_terms(self) -> None:
        for query in (
            "これは完全な文です。",
            "Esta es una oración completa.",
            "这是一个需要完整翻译的句子。",
        ):
            with self.subTest(query=query):
                self.assertFalse(cli.is_short_term(query))

    def test_prompt_requires_language_detection_and_chinese_output(self) -> None:
        prompt = cli.translation_prompt("hola mundo", "操作系统")
        self.assertIn("自动识别", prompt)
        self.assertIn("简体中文", prompt)
        self.assertIn("操作系统", prompt)

    def test_google_fallback_parses_detected_language(self) -> None:
        response = [[['你好世界', 'hola mundo', None, None]], None, 'es']
        with patch.object(cli, "json_request", return_value=response):
            result = cli.google_translate_lookup("hola mundo")
        self.assertEqual(result["translation"], "你好世界")
        self.assertEqual(result["detected_language"], "es")


if __name__ == "__main__":
    unittest.main()
