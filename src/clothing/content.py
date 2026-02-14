"""内容生成模块

将穿搭建议格式化为结构化 Markdown 内容，供 NotebookLM 消费。
"""

from datetime import datetime
from typing import Optional
from .index import ClothingAdvice


def generate_markdown(advices: list[ClothingAdvice], date: Optional[str] = None) -> str:
    """生成适合 NotebookLM infographic 的 Markdown 内容"""
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    weekday_map = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}
    dt = datetime.strptime(date, "%Y-%m-%d")
    weekday = weekday_map[dt.weekday()]

    lines = []

    lines.append(f"# 今日穿搭指南 | {date} 星期{weekday}")
    lines.append("")
    lines.append(f"每日穿搭建议，让你出门不纠结！覆盖 {len(advices)} 个城市的天气穿搭推荐。")
    lines.append("")

    lines.append("## 各城市天气总览")
    lines.append("")
    lines.append("| 城市 | 天气 | 温度范围 | 体感温度 | 穿衣等级 |")
    lines.append("|------|------|----------|----------|----------|")
    for adv in advices:
        lines.append(f"| {adv.city_name} | {adv.weather_desc} | {adv.temp_range} | {adv.feels_like} | {adv.clothing_category} |")
    lines.append("")

    lines.append("## 各城市穿搭详情")
    lines.append("")

    for adv in advices:
        lines.append(f"### {adv.city_name}")
        lines.append("")
        lines.append(f"- 天气: {adv.weather_desc}")
        lines.append(f"- 温度: {adv.temp_range}（体感 {adv.feels_like}）")
        lines.append(f"- 穿衣等级: {adv.clothing_category}")
        lines.append("")
        lines.append(f"**穿搭建议**: {adv.outfit_suggestion}")
        lines.append("")

        if adv.extra_tips:
            lines.append("**小贴士**:")
            for tip in adv.extra_tips:
                lines.append(f"- {tip}")
            lines.append("")

        if adv.api_advice:
            lines.append(f"> {adv.api_advice}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("数据来源：OpenWeatherMap | 穿搭建议仅供参考，请结合个人体质和实际情况调整")

    return "\n".join(lines)


def save_markdown(content: str, output_path: str) -> str:
    """保存 Markdown 文件"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path
