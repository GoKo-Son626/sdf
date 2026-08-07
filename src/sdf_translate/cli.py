#!/usr/bin/env python3
"""Terminal multilingual translator: configurable LLM first, free fallback."""

from __future__ import annotations

import concurrent.futures
import getpass
import json
import os
import re
import select
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import __version__
from .diagnostics import print_diagnostics
from .paths import config_file, history_file
from .providers import PROVIDER_PRESETS, free_provider_help
from .storage import SAVE_MODES, archive_result, save_mode, vocabulary_path

CONFIG_FILE = config_file()
HISTORY_FILE = history_file()

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DICTIONARY_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

ANSI = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

try:
    from opencc import OpenCC

    _TO_SIMPLIFIED = OpenCC("t2s")
except (ImportError, OSError):
    _TO_SIMPLIFIED = None


def color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if ANSI else text


def simplified_chinese(text: str) -> str:
    return _TO_SIMPLIFIED.convert(text) if _TO_SIMPLIFIED else text


def load_config() -> dict[str, str]:
    config: dict[str, str] = {}
    if CONFIG_FILE.exists():
        for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip().strip("\"'")

    # Generic environment variables take precedence.
    env_map = {
        "SDF_PROVIDER": "PROVIDER",
        "SDF_PROVIDER_NAME": "PROVIDER_NAME",
        "SDF_API_KEY": "API_KEY",
        "SDF_BASE_URL": "BASE_URL",
        "SDF_MODEL": "MODEL",
        "SDF_SAVE_MODE": "SAVE_MODE",
        "SDF_VOCABULARY_FILE": "VOCABULARY_FILE",
    }
    for env_key, config_key in env_map.items():
        if os.environ.get(env_key):
            config[config_key] = os.environ[env_key]
    for key in ("TRANSLATION_DOMAIN", "HTTPS_PROXY"):
        if os.environ.get(key):
            config[key] = os.environ[key]

    # Convenient provider-specific environment variables.
    if os.environ.get("DEEPSEEK_API_KEY"):
        config.setdefault("PROVIDER", "deepseek")
        config["API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
    if os.environ.get("ZAI_API_KEY"):
        config.setdefault("PROVIDER", "zhipu")
        config["API_KEY"] = os.environ["ZAI_API_KEY"]
    if os.environ.get("OPENAI_API_KEY") and config.get("PROVIDER") == "openai-compatible":
        config["API_KEY"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("GEMINI_API_KEY"):
        config.setdefault("PROVIDER", "gemini")
        config["API_KEY"] = os.environ["GEMINI_API_KEY"]
    if os.environ.get("GEMINI_MODEL") and config.get("PROVIDER") == "gemini":
        config["MODEL"] = os.environ["GEMINI_MODEL"]
    provider_env_keys = (
        ("GROQ_API_KEY", "groq"),
        ("OPENROUTER_API_KEY", "openrouter"),
        ("SILICONFLOW_API_KEY", "siliconflow"),
        ("GITHUB_TOKEN", "github-models"),
    )
    for env_key, provider_id in provider_env_keys:
        if os.environ.get(env_key) and config.get("PROVIDER") == provider_id:
            config["API_KEY"] = os.environ[env_key]

    # Migrate the original Gemini-only config without breaking existing users.
    if "PROVIDER" not in config and config.get("GEMINI_API_KEY"):
        config["PROVIDER"] = "gemini"
        config["PROVIDER_NAME"] = "Gemini"
        config["API_KEY"] = config["GEMINI_API_KEY"]
        config["MODEL"] = config.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    return config


def read_disk_config() -> dict[str, str]:
    disk_config: dict[str, str] = {}
    if CONFIG_FILE.exists():
        for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                disk_config[key.strip()] = value.strip().strip("\"'")
    return disk_config


def save_config_values(
    values: dict[str, str], *, clear_keys: tuple[str, ...] = ()
) -> None:
    disk_config = read_disk_config()
    for key in clear_keys:
        disk_config.pop(key, None)
    for key, value in values.items():
        cleaned = value.strip()
        if cleaned:
            disk_config[key] = cleaned
        else:
            disk_config.pop(key, None)

    lines = [
        "# This file contains private configuration. Do not share it.",
    ]
    ordered_keys = (
        "PROVIDER",
        "PROVIDER_NAME",
        "API_KEY",
        "BASE_URL",
        "MODEL",
        "TRANSLATION_DOMAIN",
        "SAVE_MODE",
        "VOCABULARY_FILE",
        "HTTPS_PROXY",
        "GLOBAL_SHORTCUT",
    )
    for key in ordered_keys:
        if disk_config.get(key):
            lines.append(f"{key}={disk_config[key]}")
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    CONFIG_FILE.chmod(0o600)


def save_provider_config(values: dict[str, str]) -> None:
    save_config_values(
        values,
        clear_keys=(
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
            "PROVIDER",
            "PROVIDER_NAME",
            "API_KEY",
            "BASE_URL",
            "MODEL",
        ),
    )


def prompt_value(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{label}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
    return value or default


SAVE_MODE_ALIASES = {
    "on": "all",
    "true": "all",
    "1": "all",
    "word": "terms",
    "words": "terms",
    "term": "terms",
    "sentence": "texts",
    "sentences": "texts",
    "text": "texts",
}


def set_vocabulary_path(raw_path: str) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(raw_path.strip())))
    if path.exists() and path.is_dir():
        path /= "vocabulary.md"
    path = path.resolve()
    save_config_values({"VOCABULARY_FILE": str(path)})
    return path


def set_save_mode(raw_mode: str) -> str | None:
    mode = SAVE_MODE_ALIASES.get(raw_mode.strip().lower(), raw_mode.strip().lower())
    if mode not in SAVE_MODES:
        return None
    save_config_values({"SAVE_MODE": mode})
    return mode


def storage_summary(config: dict[str, str]) -> str:
    path = vocabulary_path(config)
    return f"Save mode: {save_mode(config)}; vocabulary: {path or 'not set'}"


def configure_storage() -> bool:
    config = load_config()
    current_path = vocabulary_path(config)
    print()
    print(color("Configure vocabulary storage", "1;36"))
    print(f"Current path: {current_path or 'not set'}")
    raw_path = prompt_value("Markdown file path", str(current_path or ""))
    if not raw_path:
        print(color("No path was set; saving remains disabled.", "33"))
        save_config_values({"SAVE_MODE": "off", "VOCABULARY_FILE": ""})
        return True
    path = set_vocabulary_path(raw_path)

    print("  1. Disable saving (default)")
    print("  2. Save everything")
    print("  3. Save words and short terms only")
    print("  4. Save sentences and long text only")
    choices = {"1": "off", "2": "all", "3": "terms", "4": "texts"}
    current_mode = save_mode(config)
    default_choice = {value: key for key, value in choices.items()}.get(current_mode, "1")
    choice = prompt_value("Choose", default_choice)
    mode = choices.get(choice)
    if mode is None:
        print(color("Invalid choice; the save mode was not changed.", "31"))
        return False
    set_save_mode(mode)
    print(color(f"✓ Vocabulary: {path}\n✓ Save mode: {mode}", "32"))
    return True


def configure_provider() -> bool:
    while True:
        print()
        print(color("Configure an AI provider", "1;36"))
        for index, preset in enumerate(PROVIDER_PRESETS, start=1):
            free_mark = " [free]" if preset.free else ""
            print(f"  {index}. {preset.name}{free_mark} — {preset.note}")
        custom_choice = len(PROVIDER_PRESETS) + 1
        none_choice = custom_choice + 1
        print(f"  {custom_choice}. Any OpenAI-compatible endpoint")
        print(f"  {none_choice}. Keyless fallback translation only")
        print("  h. Show free API key registration help")
        try:
            choice = input("Choose [1]: ").strip().lower() or "1"
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        if choice in ("h", "help", "?"):
            print()
            print(free_provider_help())
            continue
        if choice in ("q", "quit"):
            return False
        if choice == str(none_choice):
            save_provider_config(
                {"PROVIDER": "none", "PROVIDER_NAME": "Keyless fallback"}
            )
            print(color("✓ Configured to use keyless fallback translation only.", "32"))
            return True
        if choice == str(custom_choice):
            print("Works with OpenAI, Groq, OpenRouter, GitHub Models, SiliconFlow, and similar endpoints.")
            provider_name = prompt_value("Provider name", "Custom provider")
            base_url = prompt_value("API base URL (usually ending in /v1)")
            model = prompt_value("Model name")
            if not base_url or not model:
                print(color("The base URL and model name are required.", "31"))
                return False
            values = {
                "PROVIDER": "openai-compatible",
                "PROVIDER_NAME": provider_name,
                "BASE_URL": base_url,
                "MODEL": model,
            }
            key_label = f"{provider_name} API Key"
            break
        try:
            preset = PROVIDER_PRESETS[int(choice) - 1]
        except (ValueError, IndexError):
            print(color("Invalid choice; try again.", "31"))
            continue
        print(f"API key registration: {preset.key_url}")
        print(f"Note: {preset.note}")
        model = prompt_value("Model name", preset.model)
        values = {
            "PROVIDER": preset.provider_id,
            "PROVIDER_NAME": preset.name,
            "MODEL": model,
        }
        if preset.base_url:
            values["BASE_URL"] = preset.base_url
        key_label = f"{preset.name} API Key"
        break

    print("The API key will not be displayed while you paste or type it.")
    try:
        api_key = getpass.getpass(f"{key_label}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not api_key:
        print(color("No API key entered; configuration was not changed.", "33"))
        return False
    values["API_KEY"] = api_key
    save_provider_config(values)
    print(
        color(
            f"✓ Configured {values['PROVIDER_NAME']} / {values['MODEL']}.",
            "32",
        )
    )
    return True


def json_request(
    url: str,
    *,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
) -> Any:
    body = None
    request_headers = {
        "User-Agent": (
            f"sdf-translator/{__version__} "
            "(+https://github.com/GoKo-Son626/sdf)"
        )
    }
    if headers:
        request_headers.update(headers)
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(
        url, data=body, headers=request_headers, method=method
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def readable_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8", errors="replace"))
        message = payload.get("error", {}).get("message")
        if message:
            return f"HTTP {exc.code}: {message}"
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
        pass
    common = {
        400: "invalid request parameters, model name, or API key type",
        401: "the API key is invalid or expired",
        402: "the account has insufficient credit or requires billing",
        403: "the API key lacks permission, the service is disabled, or the region is restricted",
        404: "the endpoint or model does not exist",
        429: "API credit, quota, or rate limit exceeded",
        500: "the model service reported an internal error",
        503: "the model service is temporarily busy",
    }
    return f"HTTP {exc.code}: {common.get(exc.code, exc.reason)}"


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def sensitive_input_reason(query: str) -> str | None:
    """Reject high-confidence credentials before any external API call."""
    checks = (
        (
            r"(?i)https?://\S*[?&](?:token|api[_-]?key|access[_-]?key|code)=",
            "the text contains a URL with a token or key",
        ),
        (
            r"(?i)\b(?:authorization\s*:\s*)?bearer\s+[A-Za-z0-9._~+/=-]{12,}",
            "the text contains an access token",
        ),
        (
            r"(?i)\bsk-[A-Za-z0-9_-]{16,}\b|\bAIza[A-Za-z0-9_-]{20,}\b",
            "the text contains a likely API key",
        ),
        (
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            "the text contains a private key",
        ),
        (
            r"(?i)(?:password|passwd|api[ _-]?key|access[ _-]?token|"
            r"refresh[ _-]?token|secret|\u5bc6\u7801|\u4ee4\u724c|\u5bc6\u94a5)\s*"
            r"(?:[:=\uFF1A]|is\b|\u4e3a|\u662f)\s*[\"'`]?[\w!@#$%^&*+./~=-]{8,}",
            "the text contains a likely password, key, or token",
        ),
    )
    for pattern, reason in checks:
        if re.search(pattern, query):
            return reason
    return None


def is_short_term(query: str) -> bool:
    """Treat a word or compact multilingual phrase as a term, not a sentence."""
    normalized = normalize_query(query)
    words = re.findall(r"\w+(?:['_.+-]\w+)*", normalized, flags=re.UNICODE)
    sentence_marks = re.search(r"[.!?;\u3002\uFF01\uFF1F\uFF1B]", normalized)
    return bool(words) and len(words) <= 5 and len(normalized) <= 80 and not sentence_marks


def gemini_schema(query: str) -> dict[str, Any]:
    term = is_short_term(query)
    return {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING"},
            "translations": {
                "type": "ARRAY",
                "minItems": 2 if term else 1,
                "maxItems": 3 if term else 1,
                "items": {"type": "STRING"},
                "description": "Terms return 2-3 common Simplified Chinese meanings; text returns one complete translation",
            },
        },
        "required": ["query", "translations"],
    }


def translation_prompt(query: str, domain: str) -> str:
    if is_short_term(query):
        task = (
            "The input is a word or short technical term. Return only 2-3 common "
            "Simplified Chinese meanings ordered by likelihood. Each item must be a "
            "Chinese equivalent or very short definition, without explanations, examples, "
            "or domain labels. Meanings must be genuinely distinct and common."
        )
    else:
        task = (
            "The input is a complete sentence, paragraph, or document. Return exactly one "
            "complete, coherent, and accurate Simplified Chinese translation. Do not omit "
            "any sentence or the final line. Preserve all information and paragraph logic. "
            "Do not explain, summarize, offer alternatives, or add content. The translations "
            "array must contain exactly one complete translation."
        )
    return f"""
You are a precise and concise multilingual professional translator. Detect the input language automatically and translate it into Simplified Chinese.
Use established industry terminology and prioritize the user's preferred domain. If the input is already Chinese, preserve its meaning and normalize only when necessary.
Output one valid JSON object and no Markdown or other text.

Use exactly this JSON structure:
{{
  "query": "original input",
  "translations": ["Simplified Chinese result"]
}}

Task: {task}
Preferred professional domain: {domain or "not specified; use the most common context"}
Input: {query}
""".strip()


def parse_model_json(text: str) -> dict[str, Any]:
    content = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL)
    if fenced:
        content = fenced.group(1)
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        # Some compatible models add a short preface despite the instruction.
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("the model did not return parseable JSON") from exc
        try:
            result = json.loads(content[start : end + 1])
        except json.JSONDecodeError as nested:
            raise RuntimeError("the model returned incomplete JSON") from nested
    if not isinstance(result, dict):
        raise RuntimeError("the model result is not a JSON object")
    return result


def validate_model_result(
    result: dict[str, Any], query: str, source: str
) -> dict[str, Any]:
    raw_translations = result.get("translations")
    if not isinstance(raw_translations, list):
        raw_translations = [result.get("translation", "")]
    translations: list[str] = []
    limit = 3 if is_short_term(query) else 1
    for item in raw_translations:
        text = simplified_chinese(str(item).strip())
        if text and text not in translations:
            translations.append(text)
        if len(translations) >= limit:
            break
    if not translations:
        raise RuntimeError("the model returned an empty translation")
    result["query"] = query
    result["kind"] = "term" if is_short_term(query) else "text"
    result["translations"] = translations
    result["source"] = source
    return result


def translate_with_gemini(
    query: str, domain: str, config: dict[str, str]
) -> dict[str, Any]:
    api_key = config.get("API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Gemini API key is not configured")
    model = config.get("MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    prompt = translation_prompt(query, domain)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 300 if is_short_term(query) else 2400,
            "responseMimeType": "application/json",
            "responseSchema": gemini_schema(query),
        },
    }
    url = GEMINI_URL.format(model=urllib.parse.quote(model, safe=""))
    try:
        response = json_request(
            url,
            method="POST",
            data=payload,
            headers={"x-goog-api-key": api_key},
            timeout=35,
        )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(readable_http_error(exc)) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"network connection failed: {reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("request timed out") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Gemini returned unparseable data") from exc

    try:
        candidate = response["candidates"][0]
        if candidate.get("finishReason") not in (None, "STOP"):
            raise RuntimeError(f"generation stopped: {candidate['finishReason']}")
        text = candidate["content"]["parts"][0]["text"]
        result = parse_model_json(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        block_reason = (
            response.get("promptFeedback", {}).get("blockReason")
            if isinstance(response, dict)
            else None
        )
        detail = f" ({block_reason})" if block_reason else ""
        raise RuntimeError(f"unexpected response structure{detail}") from exc

    return validate_model_result(result, query, f"Gemini ({model})")


def chat_completions_url(base_url: str) -> str:
    clean = base_url.strip().rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    return clean + "/chat/completions"


def translate_with_openai_compatible(
    query: str, domain: str, config: dict[str, str]
) -> dict[str, Any]:
    api_key = config.get("API_KEY", "").strip()
    base_url = config.get("BASE_URL", "").strip()
    model = config.get("MODEL", "").strip()
    provider_name = config.get("PROVIDER_NAME", "AI provider").strip() or "AI provider"
    if not api_key:
        raise RuntimeError(f"{provider_name} API key is not configured")
    if not base_url or not model:
        raise RuntimeError("API base URL or model name is not configured")

    prompt = translation_prompt(query, domain)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise multilingual translator. Detect the language, translate into Simplified Chinese, and return valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.15,
        "max_tokens": 300 if is_short_term(query) else 2400,
        "response_format": {"type": "json_object"},
    }
    if config.get("PROVIDER") in ("deepseek", "zhipu"):
        # Translation does not need a long reasoning trace. Both built-in
        # providers support this switch; disabling it improves latency.
        payload["thinking"] = {"type": "disabled"}
    url = chat_completions_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        try:
            response = json_request(
                url, method="POST", data=payload, headers=headers, timeout=40
            )
        except urllib.error.HTTPError as exc:
            # A few OpenAI-compatible providers do not implement JSON mode.
            if exc.code != 400 or config.get("PROVIDER") == "deepseek":
                raise
            payload.pop("response_format", None)
            payload.pop("temperature", None)
            payload.pop("max_tokens", None)
            response = json_request(
                url, method="POST", data=payload, headers=headers, timeout=40
            )
    except urllib.error.HTTPError as exc:
        raise RuntimeError(readable_http_error(exc)) from exc
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"network connection failed: {reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("request timed out") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"{provider_name} returned unparseable data") from exc

    try:
        message = response["choices"][0]["message"]
        content = message.get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("the model returned empty content")
        result = parse_model_json(content)
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("the response does not match the OpenAI Chat Completions format") from exc
    return validate_model_result(result, query, f"{provider_name} ({model})")


def provider_label(config: dict[str, str]) -> str:
    provider = config.get("PROVIDER", "")
    if provider == "none" or not provider:
        return "Keyless fallback"
    return config.get("PROVIDER_NAME") or (
        "Gemini" if provider == "gemini" else provider
    )


def translate_with_configured_model(
    query: str, domain: str, config: dict[str, str]
) -> dict[str, Any]:
    provider = config.get("PROVIDER", "")
    if provider == "gemini":
        return translate_with_gemini(query, domain, config)
    if provider not in ("", "none"):
        return translate_with_openai_compatible(query, domain, config)
    raise RuntimeError("no AI provider is configured")


def mymemory_lookup(text: str) -> dict[str, Any]:
    # The public API has a 500-byte query limit. Avoid cutting a UTF-8 sequence.
    encoded = text.encode("utf-8")
    if len(encoded) > 480:
        encoded = encoded[:480]
        while True:
            try:
                text = encoded.decode("utf-8")
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
    params = urllib.parse.urlencode({"q": text, "langpair": "en|zh-CN", "mt": "1"})
    response = json_request(f"{MYMEMORY_URL}?{params}", timeout=15)
    primary = simplified_chinese(
        str(response.get("responseData", {}).get("translatedText", "")).strip()
    )
    alternatives: list[str] = []
    for match in response.get("matches", [])[:10]:
        translated = simplified_chinese(str(match.get("translation", "")).strip())
        if translated and translated.lower() != text.lower():
            if translated not in alternatives and translated != primary:
                alternatives.append(translated)
    return {"translation": primary, "alternatives": alternatives[:3]}


def google_translate_lookup(text: str) -> dict[str, Any]:
    """Use Google's public web translation endpoint with language detection."""
    params = urllib.parse.urlencode(
        {"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text}
    )
    response = json_request(f"{GOOGLE_TRANSLATE_URL}?{params}", timeout=15)
    if not isinstance(response, list) or not response or not response[0]:
        raise RuntimeError("Google fallback returned an empty translation")
    translated = "".join(
        str(segment[0])
        for segment in response[0]
        if isinstance(segment, list) and segment and segment[0]
    )
    detected = str(response[2]) if len(response) > 2 and response[2] else ""
    return {
        "translation": simplified_chinese(translated.strip()),
        "detected_language": detected,
    }


def dictionary_lookup(word: str) -> dict[str, Any] | None:
    url = DICTIONARY_URL.format(word=urllib.parse.quote(word))
    try:
        data = json_request(url, timeout=12)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if not isinstance(data, list) or not data:
        return None
    entry = data[0]
    pronunciation = entry.get("phonetic", "")
    if not pronunciation:
        for item in entry.get("phonetics", []):
            if item.get("text"):
                pronunciation = item["text"]
                break
    senses: list[dict[str, str]] = []
    for meaning in entry.get("meanings", []):
        part = str(meaning.get("partOfSpeech", "")).strip()
        for definition in meaning.get("definitions", [])[:2]:
            text = str(definition.get("definition", "")).strip()
            if text:
                senses.append(
                    {
                        "part": part,
                        "definition": text,
                        "example": str(definition.get("example", "")).strip(),
                    }
                )
            if len(senses) >= 4:
                break
        if len(senses) >= 4:
            break
    return {"pronunciation": pronunciation, "senses": senses}


def safe_mymemory(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return mymemory_lookup(text), None
    except urllib.error.HTTPError as exc:
        return None, f"MyMemory HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"MyMemory {exc}"
    except Exception as exc:  # Keep fallback available even on unusual API data.
        return None, f"MyMemory {type(exc).__name__}: {exc}"


def safe_google_translate(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return google_translate_lookup(text), None
    except urllib.error.HTTPError as exc:
        return None, f"Google fallback HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"Google fallback {exc}"
    except Exception as exc:
        return None, f"Google fallback {type(exc).__name__}: {exc}"


def safe_dictionary(word: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return dictionary_lookup(word), None
    except urllib.error.HTTPError as exc:
        return None, f"Free Dictionary HTTP {exc.code}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"Free Dictionary {exc}"
    except Exception as exc:
        return None, f"Free Dictionary {type(exc).__name__}: {exc}"


def split_utf8_chunks(text: str, max_bytes: int = 450) -> list[str]:
    """Split without dropping words so the public fallback API stays in limit."""
    chunks: list[str] = []
    current = ""
    for token in re.findall(r"\S+\s*", text):
        candidate = current + token
        if current and len(candidate.encode("utf-8")) > max_bytes:
            chunks.append(current.strip())
            current = token
        else:
            current = candidate
        while len(current.encode("utf-8")) > max_bytes:
            encoded = current.encode("utf-8")
            cut = encoded[:max_bytes]
            while True:
                try:
                    piece = cut.decode("utf-8")
                    break
                except UnicodeDecodeError:
                    cut = cut[:-1]
            chunks.append(piece.strip())
            current = encoded[len(cut) :].decode("utf-8")
    if current.strip():
        chunks.append(current.strip())
    return chunks


def translate_with_fallback(query: str) -> dict[str, Any]:
    chunks = split_utf8_chunks(query)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(chunks))) as pool:
        responses = list(pool.map(safe_google_translate, chunks))
    failures = [error for translated, error in responses if not translated]
    if failures:
        # MyMemory remains a second keyless backup when Google is unavailable.
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(4, len(chunks))
        ) as pool:
            responses = list(pool.map(safe_mymemory, chunks))
        failures = [error for translated, error in responses if not translated]
        if failures:
            raise RuntimeError("; ".join(error or "unknown error" for error in failures))
    translated_parts = [
        str(translated.get("translation", "")).strip()
        for translated, _ in responses
        if translated
    ]
    primary = " ".join(part for part in translated_parts if part)
    translated = responses[0][0] if responses else None
    candidates = [primary]
    if is_short_term(query) and translated:
        candidates.extend(translated.get("alternatives", []))
    translations: list[str] = []
    for item in candidates:
        value = simplified_chinese(str(item).strip())
        if value and value not in translations:
            translations.append(value)
        if len(translations) >= (3 if is_short_term(query) else 1):
            break
    if not translations:
        raise RuntimeError("the fallback service returned no valid translation")
    return {
        "query": query,
        "kind": "term" if is_short_term(query) else "text",
        "translations": translations,
        "source": "Keyless machine-translation fallback",
    }


def display_result(result: dict[str, Any]) -> None:
    print()
    translations = result.get("translations", [])
    if result.get("kind") == "term":
        print(color(result.get("query", ""), "1;36"))
        print(color("; ".join(translations), "1;32"))
    else:
        print(color(translations[0] if translations else "", "1;32"))


def translate_machine(
    query: str, domain: str, config: dict[str, str]
) -> tuple[dict[str, Any], int]:
    """Translate for editor/desktop integrations and emit no human UI text."""
    query = normalize_query(query)
    if not query:
        return {"ok": False, "error": "No text was provided for translation"}, 1
    sensitive_reason = sensitive_input_reason(query)
    if sensitive_reason:
        return {
            "ok": False,
            "error": f"Translation blocked: {sensitive_reason}. The content was not sent or saved.",
        }, 1
    if len(query) > 12000:
        return {"ok": False, "error": "Input too long: the current limit is 12,000 characters"}, 1

    label = provider_label(config)
    warnings: list[str] = []
    provider = config.get("PROVIDER", "")
    if provider not in ("", "none") and config.get("API_KEY"):
        try:
            result = translate_with_configured_model(query, domain, config)
        except RuntimeError as exc:
            warnings.append(f"{label} translation failed: {exc}")
            try:
                result = translate_with_fallback(query)
            except RuntimeError as fallback_exc:
                return {
                    "ok": False,
                    "error": f"Fallback translation also failed: {fallback_exc}",
                    "warnings": warnings,
                }, 1
    else:
        warnings.append("No AI provider is configured; keyless fallback was used")
        try:
            result = translate_with_fallback(query)
        except RuntimeError as fallback_exc:
            return {
                "ok": False,
                "error": f"Fallback translation failed: {fallback_exc}",
                "warnings": warnings,
            }, 1

    archive = archive_result(result, config)
    translations = result.get("translations", [])
    payload = {
        "ok": True,
        "query": result.get("query", query),
        "kind": result.get("kind", "text"),
        "translations": translations,
        "translation": "; ".join(translations),
        "source": result.get("source", ""),
        "saved": archive.saved,
        "archive_status": archive.status,
        "vocabulary_file": str(archive.path) if archive.path else "",
        "warnings": warnings,
    }
    return payload, 0


def translate_and_save(query: str, domain: str, config: dict[str, str]) -> bool:
    query = normalize_query(query)
    if not query:
        return False
    sensitive_reason = sensitive_input_reason(query)
    if sensitive_reason:
        print(
            color(
                f"Translation blocked: {sensitive_reason}. The content was not sent or saved.",
                "31",
            )
        )
        return False
    if len(query) > 12000:
        print(color("Input too long: the current limit is 12,000 characters.", "31"))
        return False

    label = provider_label(config)
    model_error: str | None = None
    provider = config.get("PROVIDER", "")
    if provider not in ("", "none") and config.get("API_KEY"):
        try:
            print(color(f"{label} is analyzing...", "2"))
            result = translate_with_configured_model(query, domain, config)
        except RuntimeError as exc:
            model_error = str(exc)
            print(color(f"{label} translation failed: {model_error}", "31"))
            print(color("Using keyless fallback translation...", "33"))
            try:
                result = translate_with_fallback(query)
            except RuntimeError as fallback_exc:
                print(color(f"Fallback translation also failed: {fallback_exc}", "31"))
                return False
    else:
        print(color("Using keyless fallback translation...", "33"))
        try:
            result = translate_with_fallback(query)
        except RuntimeError as fallback_exc:
            print(color(f"Fallback translation failed: {fallback_exc}", "31"))
            return False

    display_result(result)
    archive = archive_result(result, config)
    if archive.status == "saved":
        print(color(f"✓ Saved to {archive.path}", "32"))
    elif archive.status == "duplicate":
        print(color("↪ An identical entry already exists; not saved again.", "33"))
    elif archive.status == "path_missing":
        print(color("Not saved: set a vocabulary path with :save-path first.", "33"))
    elif archive.status == "filtered":
        print(color("Not saved because this entry does not match the current policy.", "33"))
    return True


def setup_readline() -> None:
    try:
        import readline

        # Keep an entire multi-line terminal paste in one editable input buffer.
        readline.parse_and_bind("set enable-bracketed-paste on")
        if HISTORY_FILE.exists():
            readline.read_history_file(HISTORY_FILE)
        readline.set_history_length(300)
    except (ImportError, OSError):
        pass


def save_history() -> None:
    try:
        import readline

        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        readline.write_history_file(HISTORY_FILE)
    except (ImportError, OSError):
        pass


def read_interactive_input(prompt: str) -> str:
    """Read one query and absorb lines that arrived in the same terminal paste."""
    first = input(prompt)
    if not sys.stdin.isatty():
        return first
    lines = [first]
    # Bracketed paste handles modern terminals. This short drain is a fallback
    # for terminals that submit each pasted line separately.
    while True:
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0.12)
        except (OSError, ValueError):
            break
        if not ready:
            break
        extra = sys.stdin.readline()
        if extra == "":
            break
        lines.append(extra.rstrip("\r\n"))
    return "\n".join(lines)


def read_paste_block() -> str:
    print("Paste multiline text, then enter :end on a separate line.")
    lines: list[str] = []
    while True:
        try:
            line = input(color("... ", "2"))
        except EOFError:
            break
        if line.strip() == ":end":
            break
        lines.append(line)
    return "\n".join(lines)


HELP = """
Enter a word, technical term, phrase, sentence, or document in any language.
The result is always Simplified Chinese. For reliable multiline input, use :paste and finish with :end.

Commands:
  :paste           Start reliable multiline mode; finish with :end on its own line
  :domain <field>  Set a professional domain, for example :domain embedded systems
  :domain          Show the current domain
  :provider        Show the current provider and model
  :free-api        Show free API key registration help
  :save            Show the current vocabulary settings
  :save off|all|terms|texts  Set the save policy
  :save-path <path> Set the Markdown vocabulary path
  :settings        Configure vocabulary storage interactively
  :setup           Configure or switch providers
  :file            Show the Markdown vocabulary path
  :help            Show help
  :quit            Exit (Ctrl-D also works)

Command-line options:
  sdf --version    Show the version
  sdf --doctor     Safely inspect the environment and configuration
  sdf --hotkey [shortcut] [--force]
                   Install or change the niri/Xfce global shortcut
  sdf --hotkey-help
                   Show manual shortcut setup guidance
""".strip()


def interactive() -> int:
    config = load_config()
    if config.get("HTTPS_PROXY"):
        os.environ["HTTPS_PROXY"] = config["HTTPS_PROXY"]
        os.environ["https_proxy"] = config["HTTPS_PROXY"]
    if "PROVIDER" not in config:
        configure_provider()
        config = load_config()

    domain = config.get("TRANSLATION_DOMAIN", "")
    setup_readline()
    print(color("Multilingual professional translator", "1;36"))
    print("Enter text in any language to translate it into Chinese. Use :help for commands and :quit to exit.")
    if config.get("PROVIDER") not in ("", "none"):
        print(
            f"Current model: {provider_label(config)} / "
            f"{config.get('MODEL', 'not specified')}"
        )
    if domain:
        print(f"Current domain: {domain}")
    if config.get("PROVIDER") in ("", "none") or not config.get("API_KEY"):
        print(color("No AI provider is configured; keyless fallback will be used.", "33"))

    while True:
        try:
            raw = read_interactive_input(color("\nText> ", "1;34"))
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\nEnter :quit to exit.")
            continue
        value = raw.strip()
        if not value:
            continue
        if value == ":paste":
            value = read_paste_block().strip()
            if not value:
                continue
        if value in (":quit", ":q", "quit", "exit"):
            break
        if value in (":help", ":h"):
            print(HELP)
            continue
        if value == ":file":
            print(vocabulary_path(config) or "Vocabulary path is not set")
            continue
        if value == ":settings":
            if configure_storage():
                config = load_config()
            continue
        if value == ":setup":
            if configure_provider():
                config = load_config()
            continue
        if value == ":provider":
            if config.get("PROVIDER") in ("", "none"):
                print("Current model: not configured (keyless fallback only)")
            else:
                print(
                    f"Current model: {provider_label(config)} / "
                    f"{config.get('MODEL', 'not specified')}"
                )
            continue
        if value == ":free-api":
            print(free_provider_help())
            continue
        if value == ":domain":
            print(f"Current domain: {domain or 'not specified'}")
            continue
        if value.startswith(":domain "):
            domain = normalize_query(value[len(":domain ") :])
            print(f"Current domain set to: {domain or 'not specified'}")
            continue
        if value == ":save":
            print(storage_summary(config))
            continue
        if value.startswith(":save-path "):
            path = set_vocabulary_path(value[len(":save-path ") :])
            config = load_config()
            print(f"Vocabulary path set to: {path}")
            continue
        if value == ":save-path":
            print(vocabulary_path(config) or "Vocabulary path is not set")
            continue
        if value.startswith(":save "):
            mode = set_save_mode(value[len(":save ") :])
            if mode is None:
                print("Usage: :save off|all|terms|texts")
            else:
                config = load_config()
                print(f"Save mode set to: {mode}")
            continue
        if value.startswith(":"):
            print("Unknown command. Enter :help for help.")
            continue
        translate_and_save(value, domain, config)

    save_history()
    print("Goodbye.")
    return 0


def main() -> int:
    if len(sys.argv) == 1:
        return interactive()
    if sys.argv[1] in ("-h", "--help"):
        print("Usage: sdf [word, term, phrase, sentence, or document in any language]")
        print("Run without arguments to enter interactive mode.")
        print()
        print(HELP)
        return 0
    if sys.argv[1] in ("-V", "--version"):
        print(f"SDF Translator {__version__}")
        return 0
    if sys.argv[1] == "--doctor":
        return print_diagnostics(load_config())
    if sys.argv[1] in ("--hotkey", "--shortcut"):
        from .hotkeys import DEFAULT_SHORTCUT, configure_shortcut

        force = "--force" in sys.argv[2:]
        values = [value for value in sys.argv[2:] if value != "--force"]
        shortcut = values[0] if values else DEFAULT_SHORTCUT
        current_config = load_config()
        command = os.environ.get("SDF_GLOBAL_COMMAND", "").strip()
        if not command:
            command = shutil.which("sdf-global") or "sdf-global"
        try:
            desktop, action = configure_shortcut(
                command,
                shortcut,
                force=force,
                previous_shortcut=current_config.get("GLOBAL_SHORTCUT", ""),
            )
        except (RuntimeError, ValueError) as exc:
            print(f"Shortcut setup failed: {exc}", file=sys.stderr)
            return 1
        save_config_values({"GLOBAL_SHORTCUT": shortcut})
        print(f"{desktop} shortcut {action}: {shortcut} -> {command}")
        return 0
    if sys.argv[1] == "--hotkey-help":
        from .hotkeys import manual_shortcut_help

        command = (
            os.environ.get("SDF_GLOBAL_COMMAND", "").strip()
            or shutil.which("sdf-global")
            or "sdf-global"
        )
        print(manual_shortcut_help(command))
        return 0
    if sys.argv[1] == "--selection-write":
        from .clipboard import write_primary

        return 0 if write_primary(sys.stdin.read()) else 1
    if sys.argv[1] == "--selection-clear-if-owned":
        from .clipboard import clear_primary_if_owned

        return 0 if clear_primary_if_owned(sys.stdin.read()) else 1
    if sys.argv[1] == "--setup":
        return 0 if configure_provider() else 1
    if sys.argv[1] == "--free-api-help":
        print(free_provider_help())
        return 0
    if sys.argv[1] == "--settings":
        return 0 if configure_storage() else 1
    if sys.argv[1] == "--set-save-path":
        if len(sys.argv) < 3:
            print("Usage: sdf --set-save-path <Markdown file path>")
            return 2
        print(f"Vocabulary path set to: {set_vocabulary_path(' '.join(sys.argv[2:]))}")
        return 0
    if sys.argv[1] == "--set-save-mode":
        mode = set_save_mode(sys.argv[2]) if len(sys.argv) == 3 else None
        if mode is None:
            print("Usage: sdf --set-save-mode off|all|terms|texts")
            return 2
        print(f"Save mode set to: {mode}")
        return 0

    if sys.argv[1] == "--json":
        config = load_config()
        if config.get("HTTPS_PROXY"):
            os.environ["HTTPS_PROXY"] = config["HTTPS_PROXY"]
            os.environ["https_proxy"] = config["HTTPS_PROXY"]
        # Reading until EOF preserves a complete multi-line selection, including
        # its final line, and avoids command-line quoting/length problems.
        query = sys.stdin.read()
        if not query and len(sys.argv) > 2:
            query = " ".join(sys.argv[2:])
        payload, status = translate_machine(
            query, config.get("TRANSLATION_DOMAIN", ""), config
        )
        print(json.dumps(payload, ensure_ascii=False))
        return status

    config = load_config()
    if config.get("HTTPS_PROXY"):
        os.environ["HTTPS_PROXY"] = config["HTTPS_PROXY"]
        os.environ["https_proxy"] = config["HTTPS_PROXY"]
    query = " ".join(sys.argv[1:])
    domain = config.get("TRANSLATION_DOMAIN", "")
    if config.get("PROVIDER") in ("", "none") or not config.get("API_KEY"):
        print("Note: no AI provider is configured. Run sdf --setup to configure one.")
    return 0 if translate_and_save(query, domain, config) else 1


if __name__ == "__main__":
    raise SystemExit(main())
