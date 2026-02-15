"""二十四节气检测模块

使用 sxtwl（寿星天文历）判断给定日期是否为节气日，
并调用 GPT 动态生成节气详细内容和 infographic prompt。
如果 OPENAI_API_KEY 未配置，回退到基础信息。
"""

import json
import os
from datetime import datetime

try:
    import sxtwl
except ImportError:
    sxtwl = None

# sxtwl 节气名称顺序（索引 0~23）
JIEQI_NAMES = [
    "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
    "春分", "清明", "谷雨", "立夏", "小满", "芒种",
    "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
    "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
]

# 节气所属季节
_SEASON_MAP = {
    "立春": "春", "雨水": "春", "惊蛰": "春",
    "春分": "春", "清明": "春", "谷雨": "春",
    "立夏": "夏", "小满": "夏", "芒种": "夏",
    "夏至": "夏", "小暑": "夏", "大暑": "夏",
    "立秋": "秋", "处暑": "秋", "白露": "秋",
    "秋分": "秋", "寒露": "秋", "霜降": "秋",
    "立冬": "冬", "小雪": "冬", "大雪": "冬",
    "冬至": "冬", "小寒": "冬", "大寒": "冬",
}


# ── GPT Prompt ──

SOLAR_TERM_SYSTEM_PROMPT = """\
你是一位中国传统文化专家和信息图设计师。
给定一个二十四节气名称和日期，请生成：
1. 节气详细内容（含义、介绍、习俗、美食、养生）
2. 一段用于生成节气文化信息图的完整 prompt

节气内容要求：准确、丰富、有文化底蕴，文字优美且有感染力。

信息图 prompt 的视觉风格要求：
– 中国风水墨/工笔画与现代信息图的巧妙融合
– 节气名称以书法字体或印章形式呈现
– 融入当季自然元素（花卉、植物、动物、气象）和习俗场景
– 典雅国风色调，契合该节气的季节气质
– 包含 3-5 个核心知识点的可视化布局
– 竖版排版（PORTRAIT），印刷级清晰度

请严格以 JSON 格式返回，字段如下：
{
  "meaning": "节气的核心含义（一句话）",
  "description": "节气详细介绍（100-200字）",
  "customs": ["习俗1", "习俗2", "习俗3", "习俗4"],
  "food": "节气代表性美食（一段话）",
  "health_tip": "节气养生建议（一段话）",
  "infographic_prompt": "用于生成信息图的完整 prompt（300-500字）"
}"""

SOLAR_TERM_USER_TEMPLATE = """\
节气名称：{name}
日期：{date}
季节：{season}季

请根据此节气生成详细内容和信息图 prompt。"""


async def _generate_via_gpt(name: str, date_str: str, season: str) -> dict | None:
    """调用 GPT 生成节气内容和 infographic prompt。"""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    user_prompt = SOLAR_TERM_USER_TEMPLATE.format(
        name=name, date=date_str, season=season,
    )

    try:
        from openai import AsyncOpenAI
        from src.common.config import get_openai_config

        llm = get_openai_config()
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": SOLAR_TERM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=llm["max_completion_tokens"],
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)

        # 验证必填字段
        required = ["meaning", "description", "customs", "food", "health_tip", "infographic_prompt"]
        for key in required:
            if key not in data:
                print(f"    ⚠ GPT 返回缺少字段 '{key}'")
                return None

        if not isinstance(data["customs"], list):
            data["customs"] = [data["customs"]]

        return data

    except Exception as e:
        print(f"    ⚠ GPT 节气内容生成失败: {type(e).__name__}: {e}")
        return None


def _build_fallback(name: str, date_str: str, season: str) -> dict:
    """GPT 不可用时的基础回退。"""
    return {
        "meaning": f"{name}是二十四节气之一",
        "description": f"今日{name}，是{season}季的重要节气。",
        "customs": [f"{name}传统习俗"],
        "food": f"{name}时令饮食",
        "health_tip": f"{name}时节注意{season}季养生",
        "infographic_prompt": "",  # 为空时 main.py 会跳过 infographic 生成
    }


async def get_solar_term(date_str: str) -> dict | None:
    """判断给定日期是否为二十四节气日。

    Args:
        date_str: 日期字符串（YYYY-MM-DD）

    Returns:
        节气信息字典（含 name, date, season, meaning, description, customs,
        food, health_tip, infographic_prompt）或 None（非节气日）
    """
    if sxtwl is None:
        print("⚠ sxtwl 未安装，无法判断节气")
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    day = sxtwl.fromSolar(dt.year, dt.month, dt.day)
    if not day.hasJieQi():
        return None

    jq_index = day.getJieQi()
    jq_name = JIEQI_NAMES[jq_index]
    season = _SEASON_MAP.get(jq_name, "")

    # 尝试用 GPT 生成丰富内容
    gpt_data = await _generate_via_gpt(jq_name, date_str, season)

    if gpt_data:
        print(f"    ✨ GPT 动态生成节气内容")
        return {
            "name": jq_name,
            "date": date_str,
            "season": season,
            **gpt_data,
        }
    else:
        print(f"    📋 回退到基础节气信息")
        fallback = _build_fallback(jq_name, date_str, season)
        return {
            "name": jq_name,
            "date": date_str,
            "season": season,
            **fallback,
        }
