"""共享配置读取

从 config/config.yaml 中读取全局配置项，供各模块复用。
"""

import yaml

_CONFIG_PATH = "config/config.yaml"
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _cache = yaml.safe_load(f)
    return _cache


def get_openai_config() -> dict:
    """获取 LLM 配置，返回包含 model, max_completion_tokens, base_url 等字段的字典。

    兼容任何实现了 OpenAI API 格式的提供商（DeepSeek、Moonshot、通义千问等）。
    """
    cfg = _load()
    openai_cfg = cfg.get("openai", {})
    result = {
        "model": openai_cfg.get("model", "gpt-5"),
        "max_completion_tokens": openai_cfg.get("max_completion_tokens", 16000),
    }
    if openai_cfg.get("base_url"):
        result["base_url"] = openai_cfg["base_url"]
    return result


def get_openai_model() -> str:
    """获取 OpenAI GPT 模型名称（便捷方法）"""
    return get_openai_config()["model"]
