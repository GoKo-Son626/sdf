"""内置模型服务预设和免费接口申请说明。"""

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
        "智谱 GLM-4.7-Flash",
        "https://open.bigmodel.cn/api/paas/v4",
        "glm-4.7-flash",
        "https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
        "官方免费模型，中文与翻译场景友好",
        free=True,
    ),
    ProviderPreset(
        "groq",
        "Groq 免费层",
        "https://api.groq.com/openai/v1",
        "qwen/qwen3.6-27b",
        "https://console.groq.com/keys",
        "免费层有速率限制，推理速度快",
        free=True,
    ),
    ProviderPreset(
        "openrouter",
        "OpenRouter 免费路由",
        "https://openrouter.ai/api/v1",
        "openrouter/free",
        "https://openrouter.ai/settings/keys",
        "自动选择可用免费模型，免费额度和可用性会变化",
        free=True,
    ),
    ProviderPreset(
        "github-models",
        "GitHub 模型",
        "https://models.github.ai/inference",
        "openai/gpt-4.1",
        "https://github.com/settings/tokens",
        "GitHub 账户提供免费限速调用；PAT 需要 models:read 权限",
        free=True,
    ),
    ProviderPreset(
        "gemini",
        "谷歌 Gemini",
        "",
        "gemini-2.5-flash",
        "https://aistudio.google.com/app/apikey",
        "提供免费层，但 API 与 AI Studio 有地区限制",
        free=True,
        api_style="gemini",
    ),
    ProviderPreset(
        "siliconflow",
        "硅基流动免费模型",
        "https://api.siliconflow.cn/v1",
        "Qwen/Qwen2.5-7B-Instruct",
        "https://cloud.siliconflow.cn/account/ak",
        "平台提供若干调用价格为 0 的模型，以模型广场为准",
        free=True,
    ),
    ProviderPreset(
        "deepseek",
        "DeepSeek（深度求索）",
        "https://api.deepseek.com",
        "deepseek-v4-flash",
        "https://platform.deepseek.com/api_keys",
        "低成本付费模型；适合需要稳定专业翻译的用户",
    ),
)


def preset_by_id(provider_id: str) -> ProviderPreset | None:
    return next(
        (item for item in PROVIDER_PRESETS if item.provider_id == provider_id), None
    )


def free_provider_help() -> str:
    lines = [
        "免费 API 获取方法（免费额度、模型和地区政策可能调整）：",
        "",
    ]
    for index, preset in enumerate(
        (item for item in PROVIDER_PRESETS if item.free), start=1
    ):
        lines.extend(
            [
                f"{index}. {preset.name}",
                f"   默认模型：{preset.model}",
                f"   获取地址：{preset.key_url}",
                f"   说明：{preset.note}",
                "",
            ]
        )
    lines.append("建议优先尝试智谱、Groq 或 OpenRouter；不可用时再切换其他服务。")
    return "\n".join(lines)
