#!/usr/bin/env python3
"""Terminal English assistant: configurable LLM first, free services as fallback."""

from __future__ import annotations

import concurrent.futures
import getpass
import json
import os
import re
import select
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .paths import config_file, history_file
from .storage import SAVE_MODES, archive_result, save_mode, vocabulary_path

CONFIG_FILE = config_file()
HISTORY_FILE = history_file()

DEFAULT_PROVIDER = "deepseek"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_ZHIPU_MODEL = "glm-4.7-flash"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DICTIONARY_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"

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
        "ASDF_PROVIDER": "PROVIDER",
        "ASDF_PROVIDER_NAME": "PROVIDER_NAME",
        "ASDF_API_KEY": "API_KEY",
        "ASDF_BASE_URL": "BASE_URL",
        "ASDF_MODEL": "MODEL",
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
        "# 此文件包含私密配置，请勿分享。",
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
    return f"保存模式：{save_mode(config)}；生词本：{path or '未设置'}"


def configure_storage() -> bool:
    config = load_config()
    current_path = vocabulary_path(config)
    print()
    print(color("配置生词本", "1;36"))
    print(f"当前路径：{current_path or '未设置'}")
    raw_path = prompt_value("Markdown 文件路径", str(current_path or ""))
    if not raw_path:
        print(color("未设置路径，保存保持关闭。", "33"))
        save_config_values({"SAVE_MODE": "off", "VOCABULARY_FILE": ""})
        return True
    path = set_vocabulary_path(raw_path)

    print("  1. 关闭保存（默认）")
    print("  2. 保存全部")
    print("  3. 只保存单词和短术语")
    print("  4. 只保存句子和长文本")
    choices = {"1": "off", "2": "all", "3": "terms", "4": "texts"}
    current_mode = save_mode(config)
    default_choice = {value: key for key, value in choices.items()}.get(current_mode, "1")
    choice = prompt_value("请选择", default_choice)
    mode = choices.get(choice)
    if mode is None:
        print(color("无效选择，保存模式未改变。", "31"))
        return False
    set_save_mode(mode)
    print(color(f"✓ 生词本：{path}\n✓ 保存模式：{mode}", "32"))
    return True


def configure_provider() -> bool:
    print()
    print(color("配置大模型", "1;36"))
    print("  1. DeepSeek（推荐，默认）")
    print("  2. 智谱 GLM-4.7-Flash（免费）")
    print("  3. Gemini")
    print("  4. 任意 OpenAI 兼容接口")
    print("  5. 不使用大模型，只用免费备用翻译")
    try:
        choice = input("请选择 [1]: ").strip() or "1"
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    if choice == "5":
        save_provider_config({"PROVIDER": "none", "PROVIDER_NAME": "免费备用翻译"})
        print(color("✓ 已设置为只使用免费备用翻译。", "32"))
        return True

    if choice == "1":
        values = {
            "PROVIDER": "deepseek",
            "PROVIDER_NAME": "DeepSeek",
            "BASE_URL": DEEPSEEK_BASE_URL,
            "MODEL": DEFAULT_DEEPSEEK_MODEL,
        }
        print("API Key 获取地址：https://platform.deepseek.com/api_keys")
        key_label = "DeepSeek API Key"
    elif choice == "2":
        values = {
            "PROVIDER": "zhipu",
            "PROVIDER_NAME": "智谱 GLM",
            "BASE_URL": ZHIPU_BASE_URL,
            "MODEL": DEFAULT_ZHIPU_MODEL,
        }
        print("API Key 获取地址：https://bigmodel.cn/usercenter/proj-mgmt/apikeys")
        key_label = "智谱 API Key"
    elif choice == "3":
        values = {
            "PROVIDER": "gemini",
            "PROVIDER_NAME": "Gemini",
            "MODEL": DEFAULT_GEMINI_MODEL,
        }
        print("API Key 获取地址：https://aistudio.google.com/app/apikey")
        key_label = "Gemini API Key"
    elif choice == "4":
        print("适用于 OpenAI、硅基流动、OpenRouter、Moonshot 等兼容接口。")
        provider_name = prompt_value("服务名称", "自定义大模型")
        base_url = prompt_value("API Base URL（通常以 /v1 结尾）")
        model = prompt_value("模型名称")
        if not base_url or not model:
            print(color("Base URL 和模型名称不能为空。", "31"))
            return False
        values = {
            "PROVIDER": "openai-compatible",
            "PROVIDER_NAME": provider_name,
            "BASE_URL": base_url,
            "MODEL": model,
        }
        key_label = f"{provider_name} API Key"
    else:
        print(color("无效选择，配置未改变。", "31"))
        return False

    print("粘贴时终端不会显示字符。")
    try:
        api_key = getpass.getpass(f"{key_label}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not api_key:
        print(color("未输入 API Key，配置未改变。", "33"))
        return False
    values["API_KEY"] = api_key
    save_provider_config(values)
    print(
        color(
            f"✓ 已配置 {values['PROVIDER_NAME']} / {values['MODEL']}。",
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
    request_headers = {"User-Agent": "terminal-english-assistant/1.0"}
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
            return f"HTTP {exc.code}：{message}"
    except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
        pass
    common = {
        400: "请求参数无效，可能是模型名称或 API Key 类型不正确",
        401: "API Key 无效或已失效",
        402: "账户余额不足或需要开通计费",
        403: "API Key 没有权限、服务未开通或所在地区受限",
        404: "接口地址或模型名称不存在",
        429: "API 余额、配额或请求频率已超限",
        500: "大模型服务内部错误",
        503: "大模型服务暂时繁忙",
    }
    return f"HTTP {exc.code}：{common.get(exc.code, exc.reason)}"


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def sensitive_input_reason(query: str) -> str | None:
    """Reject high-confidence credentials before any external API call."""
    checks = (
        (
            r"(?i)https?://\S*[?&](?:token|api[_-]?key|access[_-]?key|code)=",
            "包含带令牌或密钥的链接",
        ),
        (
            r"(?i)\b(?:authorization\s*:\s*)?bearer\s+[A-Za-z0-9._~+/=-]{12,}",
            "包含访问令牌",
        ),
        (
            r"(?i)\bsk-[A-Za-z0-9_-]{16,}\b|\bAIza[A-Za-z0-9_-]{20,}\b",
            "包含疑似 API Key",
        ),
        (
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
            "包含私钥",
        ),
        (
            r"(?i)(?:password|passwd|api[ _-]?key|access[ _-]?token|"
            r"refresh[ _-]?token|secret|密码|令牌|密钥)\s*"
            r"(?:[:=：]|is\b|为|是)\s*[\"'`]?[\w!@#$%^&*+./~=-]{8,}",
            "包含疑似密码、密钥或令牌",
        ),
    )
    for pattern, reason in checks:
        if re.search(pattern, query):
            return reason
    return None


def is_short_term(query: str) -> bool:
    """Treat a word or compact technical phrase as a term, not a sentence."""
    normalized = normalize_query(query)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_.+-]*", normalized)
    sentence_marks = re.search(r"[.!?;。！？；]", normalized)
    return bool(words) and len(words) <= 5 and len(normalized) <= 80 and not sentence_marks


def gemini_schema() -> dict[str, Any]:
    return {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING"},
            "translations": {
                "type": "ARRAY",
                "minItems": 1,
                "maxItems": 4,
                "items": {"type": "STRING"},
                "description": "术语模式返回1到4个简短中文意思；文本模式只返回完整译文一个元素",
            },
        },
        "required": ["query", "translations"],
    }


def translation_prompt(query: str, domain: str) -> str:
    if is_short_term(query):
        task = (
            "这是单词或短专业术语。只给出按可能性排序的 1～4 个简短中文意思。"
            "每个元素只能是中文译词或很短的释义，不要解释、不要例句、不要领域标签。"
            "不同元素必须是真正不同且常用的含义，不要为了凑数添加冷僻含义。"
        )
    else:
        task = (
            "这是完整句子、段落或文章。只给出一份完整、连贯、准确的简体中文译文。"
            "不得遗漏任何一句，包括输入的最后一行。保持原文信息和段落逻辑，"
            "不要解释、不要总结、不要列出多个版本，也不要添加原文没有的内容。"
            "translations 数组必须且只能包含这一个完整译文。"
        )
    return f"""
你是一名严谨、简洁的英汉专业翻译。使用业界通行译名，并优先采用用户指定领域的语境。
只输出一个合法 JSON 对象，不要输出 Markdown 或 JSON 之外的文字。

JSON 必须使用这个结构：
{{
  "query": "原始输入",
  "translations": ["中文结果"]
}}

具体任务：{task}
用户偏好的专业领域：{domain or "未指定，按常见语境综合判断"}
用户输入：{query}
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
            raise RuntimeError("模型没有返回可解析的 JSON") from exc
        try:
            result = json.loads(content[start : end + 1])
        except json.JSONDecodeError as nested:
            raise RuntimeError("模型返回的 JSON 格式不完整") from nested
    if not isinstance(result, dict):
        raise RuntimeError("模型返回的结果不是 JSON 对象")
    return result


def validate_model_result(
    result: dict[str, Any], query: str, source: str
) -> dict[str, Any]:
    raw_translations = result.get("translations")
    if not isinstance(raw_translations, list):
        raw_translations = [result.get("translation", "")]
    translations: list[str] = []
    limit = 4 if is_short_term(query) else 1
    for item in raw_translations:
        text = simplified_chinese(str(item).strip())
        if text and text not in translations:
            translations.append(text)
        if len(translations) >= limit:
            break
    if not translations:
        raise RuntimeError("模型返回的翻译内容为空")
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
        raise RuntimeError("尚未配置 Gemini API Key")
    model = config.get("MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    prompt = translation_prompt(query, domain)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 300 if is_short_term(query) else 2400,
            "responseMimeType": "application/json",
            "responseSchema": gemini_schema(),
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
        raise RuntimeError(f"网络连接失败：{reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("请求超时") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Gemini 返回了无法解析的数据") from exc

    try:
        candidate = response["candidates"][0]
        if candidate.get("finishReason") not in (None, "STOP"):
            raise RuntimeError(f"生成被中止：{candidate['finishReason']}")
        text = candidate["content"]["parts"][0]["text"]
        result = parse_model_json(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        block_reason = (
            response.get("promptFeedback", {}).get("blockReason")
            if isinstance(response, dict)
            else None
        )
        detail = f"（{block_reason}）" if block_reason else ""
        raise RuntimeError(f"返回内容结构异常{detail}") from exc

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
    provider_name = config.get("PROVIDER_NAME", "大模型").strip() or "大模型"
    if not api_key:
        raise RuntimeError(f"尚未配置 {provider_name} API Key")
    if not base_url or not model:
        raise RuntimeError("API Base URL 或模型名称未配置")

    prompt = translation_prompt(query, domain)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是严谨、简洁的英汉专业翻译，只返回合法 JSON。",
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
        raise RuntimeError(f"网络连接失败：{reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("请求超时") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"{provider_name} 返回了无法解析的数据") from exc

    try:
        message = response["choices"][0]["message"]
        content = message.get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("模型返回内容为空")
        result = parse_model_json(content)
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("返回内容不符合 OpenAI Chat Completions 格式") from exc
    return validate_model_result(result, query, f"{provider_name} ({model})")


def provider_label(config: dict[str, str]) -> str:
    provider = config.get("PROVIDER", "")
    if provider == "none" or not provider:
        return "免费备用翻译"
    return config.get("PROVIDER_NAME") or (
        "Gemini" if provider == "gemini" else provider
    )


def translate_with_configured_model(
    query: str, domain: str, config: dict[str, str]
) -> dict[str, Any]:
    provider = config.get("PROVIDER", "")
    if provider == "gemini":
        return translate_with_gemini(query, domain, config)
    if provider in ("deepseek", "zhipu", "openai-compatible"):
        return translate_with_openai_compatible(query, domain, config)
    raise RuntimeError("尚未配置大模型")


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
        responses = list(pool.map(safe_mymemory, chunks))
    failures = [error for translated, error in responses if not translated]
    if failures:
        raise RuntimeError("；".join(error or "未知错误" for error in failures))
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
        if len(translations) >= (4 if is_short_term(query) else 1):
            break
    if not translations:
        raise RuntimeError("免费翻译服务没有返回有效译文")
    return {
        "query": query,
        "kind": "term" if is_short_term(query) else "text",
        "translations": translations,
        "source": "MyMemory（免费备用）",
    }


def display_result(result: dict[str, Any]) -> None:
    print()
    translations = result.get("translations", [])
    if result.get("kind") == "term":
        print(color(result.get("query", ""), "1;36"))
        print(color("；".join(translations), "1;32"))
    else:
        print(color(translations[0] if translations else "", "1;32"))


def translate_machine(
    query: str, domain: str, config: dict[str, str]
) -> tuple[dict[str, Any], int]:
    """Translate for editor/desktop integrations and emit no human UI text."""
    query = normalize_query(query)
    if not query:
        return {"ok": False, "error": "没有收到可翻译的文字"}, 1
    sensitive_reason = sensitive_input_reason(query)
    if sensitive_reason:
        return {
            "ok": False,
            "error": f"已阻止翻译：{sensitive_reason}。内容未发送给 AI，也未保存。",
        }, 1
    if len(query) > 12000:
        return {"ok": False, "error": "输入过长：目前最多支持 12000 个字符"}, 1

    label = provider_label(config)
    warnings: list[str] = []
    provider = config.get("PROVIDER", "")
    if provider not in ("", "none") and config.get("API_KEY"):
        try:
            result = translate_with_configured_model(query, domain, config)
        except RuntimeError as exc:
            warnings.append(f"{label} 翻译失败：{exc}")
            try:
                result = translate_with_fallback(query)
            except RuntimeError as fallback_exc:
                return {
                    "ok": False,
                    "error": f"备用翻译也失败：{fallback_exc}",
                    "warnings": warnings,
                }, 1
    else:
        warnings.append("尚未配置大模型，已使用免费备用翻译")
        try:
            result = translate_with_fallback(query)
        except RuntimeError as fallback_exc:
            return {
                "ok": False,
                "error": f"备用翻译失败：{fallback_exc}",
                "warnings": warnings,
            }, 1

    archive = archive_result(result, config)
    translations = result.get("translations", [])
    payload = {
        "ok": True,
        "query": result.get("query", query),
        "kind": result.get("kind", "text"),
        "translations": translations,
        "translation": "；".join(translations),
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
                f"已阻止翻译：{sensitive_reason}。内容未发送给 AI，也未保存。",
                "31",
            )
        )
        return False
    if len(query) > 12000:
        print(color("输入过长：目前最多支持 12000 个字符。", "31"))
        return False

    label = provider_label(config)
    model_error: str | None = None
    provider = config.get("PROVIDER", "")
    if provider not in ("", "none") and config.get("API_KEY"):
        try:
            print(color(f"{label} 正在分析…", "2"))
            result = translate_with_configured_model(query, domain, config)
        except RuntimeError as exc:
            model_error = str(exc)
            print(color(f"{label} 翻译失败：{model_error}", "31"))
            print(color("正在使用免费备用翻译…", "33"))
            try:
                result = translate_with_fallback(query)
            except RuntimeError as fallback_exc:
                print(color(f"备用翻译也失败：{fallback_exc}", "31"))
                return False
    else:
        print(color("正在使用免费备用翻译…", "33"))
        try:
            result = translate_with_fallback(query)
        except RuntimeError as fallback_exc:
            print(color(f"备用翻译也失败：{fallback_exc}", "31"))
            return False

    display_result(result)
    archive = archive_result(result, config)
    if archive.status == "saved":
        print(color(f"✓ 已保存到 {archive.path}", "32"))
    elif archive.status == "duplicate":
        print(color("↪ 已存在相同记录，不重复保存。", "33"))
    elif archive.status == "path_missing":
        print(color("未保存：请先使用 :save-path 设置生词本路径。", "33"))
    elif archive.status == "filtered":
        print(color("本条不符合当前保存类型，未保存。", "33"))
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
    print("请粘贴多行英文；完成后另起一行输入 :end")
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
直接输入英文单词、专业术语、短语或句子并回车。
可直接粘贴多行文本；如终端仍会拆行，先输入 :paste，最后输入 :end。

命令：
  :paste           可靠的多行粘贴模式，以单独一行 :end 结束
  :domain <领域>  设置当前专业领域，例如 :domain embedded systems
  :domain          查看当前领域
  :provider        查看当前大模型和模型名称
  :save             查看当前保存设置
  :save off|all|terms|texts  设置保存类型
  :save-path <路径> 设置 Markdown 生词本路径
  :settings         交互配置生词本
  :setup           配置或切换大模型
  :file            显示 Markdown 生词本路径
  :help            显示帮助
  :quit            退出（也可以按 Ctrl-D）
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
    print(color("English 专业翻译助手", "1;36"))
    print("输入英文即可翻译；输入 :help 查看命令，:quit 退出。")
    if config.get("PROVIDER") not in ("", "none"):
        print(
            f"当前模型：{provider_label(config)} / "
            f"{config.get('MODEL', '未指定')}"
        )
    if domain:
        print(f"当前领域：{domain}")
    if config.get("PROVIDER") in ("", "none") or not config.get("API_KEY"):
        print(color("大模型未配置，本次会使用免费备用翻译。", "33"))

    while True:
        try:
            raw = read_interactive_input(color("\nEnglish> ", "1;34"))
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n输入 :quit 退出。")
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
            print(vocabulary_path(config) or "尚未设置生词本路径")
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
                print("当前模型：未配置（只使用免费备用翻译）")
            else:
                print(
                    f"当前模型：{provider_label(config)} / "
                    f"{config.get('MODEL', '未指定')}"
                )
            continue
        if value == ":domain":
            print(f"当前领域：{domain or '未指定'}")
            continue
        if value.startswith(":domain "):
            domain = normalize_query(value[len(":domain ") :])
            print(f"当前领域已设为：{domain or '未指定'}")
            continue
        if value == ":save":
            print(storage_summary(config))
            continue
        if value.startswith(":save-path "):
            path = set_vocabulary_path(value[len(":save-path ") :])
            config = load_config()
            print(f"生词本路径已设为：{path}")
            continue
        if value == ":save-path":
            print(vocabulary_path(config) or "尚未设置生词本路径")
            continue
        if value.startswith(":save "):
            mode = set_save_mode(value[len(":save ") :])
            if mode is None:
                print("用法：:save off|all|terms|texts")
            else:
                config = load_config()
                print(f"保存模式已设为：{mode}")
            continue
        if value.startswith(":"):
            print("未知命令。输入 :help 查看帮助。")
            continue
        translate_and_save(value, domain, config)

    save_history()
    print("再见。")
    return 0


def main() -> int:
    if len(sys.argv) == 1:
        return interactive()
    if sys.argv[1] in ("-h", "--help"):
        print("用法：sdf [英文单词、术语、短语或句子]")
        print("不带参数时进入交互模式。")
        print()
        print(HELP)
        return 0
    if sys.argv[1] == "--setup":
        return 0 if configure_provider() else 1
    if sys.argv[1] == "--settings":
        return 0 if configure_storage() else 1
    if sys.argv[1] == "--set-save-path":
        if len(sys.argv) < 3:
            print("用法：sdf --set-save-path <Markdown 文件路径>")
            return 2
        print(f"生词本路径已设为：{set_vocabulary_path(' '.join(sys.argv[2:]))}")
        return 0
    if sys.argv[1] == "--set-save-mode":
        mode = set_save_mode(sys.argv[2]) if len(sys.argv) == 3 else None
        if mode is None:
            print("用法：sdf --set-save-mode off|all|terms|texts")
            return 2
        print(f"保存模式已设为：{mode}")
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
        print("提示：尚未配置大模型。运行 sdf --setup 可配置。")
    return 0 if translate_and_save(query, domain, config) else 1


if __name__ == "__main__":
    raise SystemExit(main())
