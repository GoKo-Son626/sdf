import unittest
from unittest.mock import patch

from sdf_translate import cli


class MultilingualTranslationTests(unittest.TestCase):
    def test_terms_are_detected_across_writing_systems(self) -> None:
        for query in ("virtualization", "condición de carrera", "virtualisation", "سباق البيانات"):
            with self.subTest(query=query):
                self.assertTrue(cli.is_short_term(query))

    def test_sentences_are_not_detected_as_terms(self) -> None:
        for query in (
            "Dies ist ein vollständiger Satz.",
            "Esta es una oración completa.",
            "This is a complete sentence that requires translation.",
        ):
            with self.subTest(query=query):
                self.assertFalse(cli.is_short_term(query))

    def test_prompt_requires_language_detection_and_chinese_output(self) -> None:
        prompt = cli.translation_prompt("hola mundo", "operating systems")
        self.assertIn("Detect the input language automatically", prompt)
        self.assertIn("Simplified Chinese", prompt)
        self.assertIn("2-3", prompt)
        self.assertIn("operating systems", prompt)

    def test_term_schema_requests_two_to_three_meanings(self) -> None:
        term_schema = cli.gemini_schema("race condition")
        text_schema = cli.gemini_schema("This is a complete sentence.")
        self.assertEqual(term_schema["properties"]["translations"]["minItems"], 2)
        self.assertEqual(term_schema["properties"]["translations"]["maxItems"], 3)
        self.assertEqual(text_schema["properties"]["translations"]["maxItems"], 1)

    def test_model_term_result_is_limited_to_three_meanings(self) -> None:
        result = cli.validate_model_result(
            {"translations": ["meaning one", "meaning two", "meaning three", "rare meaning"]},
            "race condition",
            "test",
        )
        self.assertEqual(
            result["translations"], ["meaning one", "meaning two", "meaning three"]
        )

    def test_sentence_result_keeps_only_one_translation(self) -> None:
        result = cli.validate_model_result(
            {"translations": ["First translation.", "Second translation."]},
            "This is a complete sentence.",
            "test",
        )
        self.assertEqual(result["translations"], ["First translation."])

    def test_google_fallback_parses_detected_language(self) -> None:
        response = [[["hello world", "hola mundo", None, None]], None, "es"]
        with patch.object(cli, "json_request", return_value=response):
            result = cli.google_translate_lookup("hola mundo")
        self.assertEqual(result["translation"], "hello world")
        self.assertEqual(result["detected_language"], "es")


if __name__ == "__main__":
    unittest.main()
