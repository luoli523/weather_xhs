"""诗词检测模块 — 使用 OpenAI GPT 动态匹配当天日期相关的唐诗宋词

流程：
  1. 计算当天的农历日期、节气等上下文
  2. 调用 GPT-4o-mini，让模型判断今天是否有相关经典诗词
  3. 如有，返回结构化的诗词数据（全文、赏析、风俗、infographic prompt）
"""

import json
import os
from datetime import datetime

WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# ── System Prompt ──

SYSTEM_PROMPT = """\
你是一位中国古典文学专家和文化学者。给定一个日期（含公历、农历、节气等信息），
请判断这个日期是否与某首著名的唐诗宋词（或极经典的先秦/魏晋诗词）有特殊关联。

关联的类型包括但不限于：
- 传统节日（春节、元宵、清明、端午、七夕、中秋、重阳、除夕、寒食等）
- 二十四节气（立春、雨水、清明、冬至等）
- 现代节日可用古典诗词呼应（情人节→鹊桥仙、母亲节→游子吟、教师节→绿野堂等）
- 历史事件纪念日、诗人诞辰/忌日等

判断规则：
1. 如果有多首相关诗词，选择最著名、传颂度最高的那一首
2. 如果当天确实没有任何相关的著名诗词，返回 has_poem: false
3. 诗词全文必须完整准确，不得删减或篡改
4. 赏析要通俗易懂，300-500字，兼顾文学性和科普性
5. 风俗科普要具体实用，每条30-60字

当 has_poem 为 true 时，你还需要生成一段用于 NotebookLM 生成信息图的 prompt（infographic_prompt 字段）。
生成 infographic_prompt 时请遵循以下视觉风格指引：
- 中国古典书画风（水墨/工笔）与现代信息图融合
- 诗词全文以书法形式呈现，作为视觉焦点
- 配合诗词意境和节日场景的插画元素（如中秋配月亮、元宵配灯笼、清明配杏花雨）
- 包含诗词赏析摘要和风俗知识的信息区块
- 整体配色契合诗词的季节和情感基调
- 印章、窗棂、山水等中国传统元素作为点缀
- 竖版排版（PORTRAIT），印刷级清晰度，典雅精致
- infographic_prompt 应为完整的、可直接提交给信息图生成工具的指令，300-500字

你必须以严格的 JSON 格式返回，schema 如下：
{
  "has_poem": boolean,
  "occasion": string,       // 节日/节气/纪念日名称，has_poem=false 时为空字符串
  "title": string,          // 诗词标题，如"水调歌头·明月几时有"
  "author": string,         // 作者
  "dynasty": string,        // 朝代
  "full_text": string,      // 诗词完整全文
  "meaning": string,        // 诗词赏析（300-500字）
  "customs": [string],      // 相关风俗科普（3-5条）
  "infographic_prompt": string  // NotebookLM 信息图生成 prompt
}

has_poem=false 时，除 has_poem 和 occasion 外的字段用空字符串或空数组。"""

# ── User Prompt Template ──

USER_PROMPT_TEMPLATE = """\
今天是 {date}（{weekday}）。
{extra_context}
请判断今天是否有相关的经典唐诗宋词，如果有，请返回完整信息。"""


def _build_extra_context(date_str: str) -> str:
    """构建农历、节气等额外上下文信息，帮助 GPT 更准确判断。"""
    parts = []

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return ""

    # 农历日期
    try:
        from zhdate import ZhDate

        zh = ZhDate.from_datetime(dt)
        lunar_month = zh.lunar_month
        lunar_day = zh.lunar_day
        parts.append(f"农历：{lunar_month}月{lunar_day}日")

        # 标注一些已知的农历节日
        lunar_festivals = {
            (1, 1): "春节（正月初一）",
            (1, 15): "元宵节（正月十五）",
            (3, 3): "上巳节（三月三）",
            (5, 5): "端午节（五月初五）",
            (7, 7): "七夕（七月初七）",
            (7, 15): "中元节（七月十五）",
            (8, 15): "中秋节（八月十五）",
            (9, 9): "重阳节（九月初九）",
            (12, 30): "除夕（腊月三十）",
            (12, 29): "除夕（腊月二十九，小月年份）",
        }
        festival = lunar_festivals.get((lunar_month, lunar_day))
        if festival:
            parts.append(f"今天是{festival}")
    except ImportError:
        pass
    except Exception:
        pass

    # 节气
    try:
        import sxtwl

        day = sxtwl.fromSolar(dt.year, dt.month, dt.day)
        if day.hasJieQi():
            jq_names = [
                "冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
                "春分", "清明", "谷雨", "立夏", "小满", "芒种",
                "夏至", "小暑", "大暑", "立秋", "处暑", "白露",
                "秋分", "寒露", "霜降", "立冬", "小雪", "大雪",
            ]
            jq_index = day.getJieQi()
            jq_name = jq_names[jq_index]
            parts.append(f"今天是二十四节气之「{jq_name}」")
    except ImportError:
        pass
    except Exception:
        pass

    # 固定日期的现代节日
    mm_dd = dt.strftime("%m-%d")
    fixed_occasions = {
        "01-01": "元旦（公历新年）",
        "02-14": "情人节",
        "03-08": "国际妇女节",
        "05-01": "国际劳动节",
        "05-04": "青年节",
        "06-01": "儿童节",
        "09-10": "教师节",
        "10-01": "国庆节",
        "12-25": "圣诞节",
    }
    occasion = fixed_occasions.get(mm_dd)
    if occasion:
        parts.append(f"今天是{occasion}")

    # 母亲节（5月第二个周日）
    if dt.month == 5 and dt.weekday() == 6:
        # 计算是第几个周日
        first_day = dt.replace(day=1)
        first_sunday = first_day.day + (6 - first_day.weekday()) % 7
        if first_sunday == 0:
            first_sunday = 7
        second_sunday = first_sunday + 7
        if dt.day == second_sunday:
            parts.append("今天是母亲节（5月第二个星期日）")

    # 父亲节（6月第三个周日）
    if dt.month == 6 and dt.weekday() == 6:
        first_day = dt.replace(day=1)
        first_sunday = first_day.day + (6 - first_day.weekday()) % 7
        if first_sunday == 0:
            first_sunday = 7
        third_sunday = first_sunday + 14
        if dt.day == third_sunday:
            parts.append("今天是父亲节（6月第三个星期日）")

    if not parts:
        parts.append("今天没有特别的节日或节气")

    return "\n".join(parts)


async def get_poem(date_str: str) -> dict | None:
    """调用 GPT 判断当天是否有相关诗词，返回完整内容或 None。

    Args:
        date_str: 日期字符串（YYYY-MM-DD）

    Returns:
        诗词信息字典（含 title, author, dynasty, full_text, meaning,
        customs, infographic_prompt, occasion, date）或 None
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    weekday = WEEKDAY_NAMES[dt.weekday()]
    extra_context = _build_extra_context(date_str)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        date=date_str,
        weekday=weekday,
        extra_context=extra_context,
    )

    try:
        from openai import AsyncOpenAI
        from src.common.config import get_openai_config

        llm = get_openai_config()
        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=llm["max_completion_tokens"],
        )

        content = response.choices[0].message.content
        if not content:
            print("  ⚠ GPT 返回为空")
            return None

        data = json.loads(content)

        if not data.get("has_poem", False):
            return None

        # 补充 date 字段
        data["date"] = date_str

        # 验证必要字段
        required_fields = ["title", "author", "dynasty", "full_text", "meaning",
                           "customs", "infographic_prompt", "occasion"]
        for field in required_fields:
            if field not in data:
                print(f"  ⚠ GPT 返回缺少字段: {field}")
                return None

        return data

    except ImportError:
        print("  ⚠ openai 库未安装，无法使用诗词模块")
        return None
    except json.JSONDecodeError as e:
        print(f"  ⚠ GPT 返回 JSON 解析失败: {e}")
        return None
    except Exception as e:
        print(f"  ⚠ 诗词检测出错: {type(e).__name__}: {e}")
        return None
