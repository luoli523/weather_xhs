"""共享配置读取

从 config/config.yaml 和环境变量中读取全局配置项，供各模块复用。

LLM 厂商通过 .env 中的 LLM_PROVIDER 选择，各厂商的 base_url 和默认模型内置于此。
"""

import os

import yaml

_CONFIG_PATH = "config/config.yaml"
_cache: dict | None = None

# 各 LLM 厂商的内置配置：env_key（API Key 环境变量名）、base_url、default_model
_LLM_PROVIDERS: dict[str, dict] = {
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": None,  # 使用 openai 库默认值
        "default_model": "gpt-4o",
    },
    "deepseek": {
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
    },
    "moonshot": {
        "env_key": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
    },
    "qwen": {
        "env_key": "QWEN_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
    },
    "grok": {
        "env_key": "GROK_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-3-mini",
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
    },
    "claude": {
        "env_key": "CLAUDE_API_KEY",
        "base_url": "https://api.anthropic.com/v1/",
        "default_model": "claude-sonnet-4-20250514",
    },
}


def _load() -> dict:
    global _cache
    if _cache is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _cache = yaml.safe_load(f)
    return _cache


def get_llm_provider() -> str:
    """获取当前选择的 LLM 厂商名称"""
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def get_llm_config() -> dict:
    """根据 LLM_PROVIDER 环境变量返回完整的 LLM 配置。

    Returns:
        {
            "provider": str,          # 厂商名称
            "api_key": str,           # API Key（可能为空）
            "base_url": str | None,   # API 端点（None 表示使用默认）
            "model": str,             # 模型名称
            "max_completion_tokens": int,
        }
    """
    provider = get_llm_provider()
    provider_cfg = _LLM_PROVIDERS.get(provider)
    if not provider_cfg:
        supported = ", ".join(_LLM_PROVIDERS.keys())
        raise ValueError(f"不支持的 LLM_PROVIDER: '{provider}'，支持: {supported}")

    api_key = os.getenv(provider_cfg["env_key"], "").strip()

    cfg = _load()
    llm_cfg = cfg.get("llm", {})

    return {
        "provider": provider,
        "api_key": api_key,
        "base_url": provider_cfg["base_url"],
        "model": llm_cfg.get("model") or provider_cfg["default_model"],
        "max_completion_tokens": llm_cfg.get("max_completion_tokens", 16000),
    }


def get_llm_model() -> str:
    """获取当前 LLM 模型名称（便捷方法）"""
    return get_llm_config()["model"]


# 向后兼容别名
get_openai_config = get_llm_config
get_openai_model = get_llm_model
