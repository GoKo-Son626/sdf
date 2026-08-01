"""Built-in provider presets and free API onboarding information."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    provider_id: str
    name: str
    base_url: str
    model: str
    key_url: str
    note: str
    free: bool = False
    api_style: str = "openai"


PROVIDER_PRESETS = (
    ProviderPreset(
        "zhipu",
        "Zhipu GLM-4.7-Flash",
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4.7-flash",
        "https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
        "Official free model with strong Chinese and translation performance",
        free=True,
    ),
    ProviderPreset(
        "groq",
        "Groq Free",
        "https://api.groq.com/openai/v1",
        "qwen/qwen3.6-27b",
        "https://console.groq.com/keys",
        "Fast inference with a rate-limited free tier",
        free=True,
    ),
    ProviderPreset(
        "openrouter",
        "OpenRouter Free Router",
        "https://openrouter.ai/api/v1",
        "openrouter/free",
        "https://openrouter.ai/settings/keys",
        "Automatically routes to an available free model; availability varies",
        free=True,
    ),
    ProviderPreset(
        "github-models",
        "GitHub Models",
        "https://models.github.ai/inference",
        "openai/gpt-4.1",
        "https://github.com/settings/tokens",
        "Rate-limited access for GitHub users; the PAT needs models:read",
        free=True,
    ),
    ProviderPreset(
        "gemini",
        "Google Gemini",
        "",
        "gemini-2.5-flash",
        "https://aistudio.google.com/app/apikey",
        "Offers a free tier, with regional restrictions for the API and AI Studio",
        free=True,
        api_style="gemini",
    ),
    ProviderPreset(
        "siliconflow",
        "SiliconFlow Free Models",
        "https://api.siliconflow.cn/v1",
        "Qwen/Qwen2.5-7B-Instruct",
        "https://cloud.siliconflow.cn/account/ak",
        "Several zero-cost models are available; consult the provider's model catalog",
        free=True,
    ),
    ProviderPreset(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com",
        "deepseek-v4-flash",
        "https://platform.deepseek.com/api_keys",
        "Low-cost paid models suitable for stable professional translation",
    ),
)


def preset_by_id(provider_id: str) -> ProviderPreset | None:
    return next(
        (item for item in PROVIDER_PRESETS if item.provider_id == provider_id), None
    )


def free_provider_help() -> str:
    lines = [
        "Free API registration (quotas, models, and regional policies may change):",
        "",
    ]
    for index, preset in enumerate(
        (item for item in PROVIDER_PRESETS if item.free), start=1
    ):
        lines.extend(
            [
                f"{index}. {preset.name}",
                f"   Default model: {preset.model}",
                f"   Registration: {preset.key_url}",
                f"   Note: {preset.note}",
                "",
            ]
        )
    lines.append(
        "Try Zhipu, Groq, or OpenRouter first, then switch providers if unavailable."
    )
    return "\n".join(lines)
