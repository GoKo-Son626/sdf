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
        self.assertIn("2～3", prompt)
        self.assertIn("操作系统", prompt)

    def test_term_schema_requests_two_to_three_meanings(self) -> None:
        term_schema = cli.gemini_schema("race condition")
        text_schema = cli.gemini_schema("This is a complete sentence.")
        self.assertEqual(term_schema["properties"]["translations"]["minItems"], 2)
        self.assertEqual(term_schema["properties"]["translations"]["maxItems"], 3)
        self.assertEqual(text_schema["properties"]["translations"]["maxItems"], 1)

    def test_model_term_result_is_limited_to_three_meanings(self) -> None:
        result = cli.validate_model_result(
            {"translations": ["竞态条件", "竞争条件", "竞争状态", "冷僻释义"]},
            "race condition",
            "test",
        )
        self.assertEqual(
            result["translations"], ["竞态条件", "竞争条件", "竞争状态"]
        )

    def test_sentence_result_keeps_only_one_translation(self) -> None:
        result = cli.validate_model_result(
            {"translations": ["第一份译文。", "第二份译文。"]},
            "This is a complete sentence.",
            "test",
        )
        self.assertEqual(result["translations"], ["第一份译文。"])

    def test_google_fallback_parses_detected_language(self) -> None:
        response = [[['你好世界', 'hola mundo', None, None]], None, 'es']
        with patch.object(cli, "json_request", return_value=response):
            result = cli.google_translate_lookup("hola mundo")
        self.assertEqual(result["translation"], "你好世界")
        self.assertEqual(result["detected_language"], "es")


if __name__ == "__main__":
    unittest.main()
