import unittest
from unittest.mock import patch

from sdf_translate import cli
from sdf_translate.providers import PROVIDER_PRESETS, free_provider_help


class ProviderPresetTests(unittest.TestCase):
    def test_http_user_agent_uses_current_project_identity(self) -> None:
        request = None

        def capture(request_value, timeout):
            nonlocal request
            request = request_value
            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return None

                def read(self):
                    return b"{}"

            return Response()

        with patch.object(cli.urllib.request, "urlopen", side_effect=capture):
            cli.json_request("https://example.invalid")
        self.assertIsNotNone(request)
        user_agent = request.get_header("User-agent")
        self.assertIn("sdf-translator/", user_agent)
        self.assertIn("GoKo-Son626/sdf", user_agent)

    def test_provider_ids_are_unique(self) -> None:
        ids = [item.provider_id for item in PROVIDER_PRESETS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 7)

    def test_free_help_has_key_urls_without_credentials(self) -> None:
        help_text = free_provider_help()
        self.assertIn("OpenRouter", help_text)
        self.assertIn("Groq", help_text)
        self.assertIn("GitHub Models", help_text)
        self.assertNotIn("Bearer ", help_text)

    def test_builtin_openai_compatible_provider_is_routed(self) -> None:
        config = {"PROVIDER": "groq", "API_KEY": "placeholder"}
        with patch.object(
            cli,
            "translate_with_openai_compatible",
            return_value={"translations": ["测试"]},
        ) as translate:
            result = cli.translate_with_configured_model("test", "", config)
        self.assertEqual(result["translations"], ["测试"])
        translate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
