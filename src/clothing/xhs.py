"""穿搭小红书内容构建与发布

构建穿搭笔记的标题、正文、标签（含特殊日子祝福），
并调用 common.xhs.publish_note() 完成自动化发布。
"""

from datetime import datetime
from pathlib import Path

import yaml

from src.common.xhs import get_xhs_config, publish_note
from .index import ClothingAdvice


# ── 特殊日子（节日祝福）逻辑 ──


def _load_special_days(config_path: str = "config/special_days.yaml") -> dict:
    """加载固定日期节日配置"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("fixed", {})
    except FileNotFoundError:
        return {}


def _lunar_special_days(year: int) -> dict[str, dict]:
    """计算农历节日对应的公历日期（每年不同）。"""
    try:
        from zhdate import ZhDate
    except ImportError:
        return {}

    lunar_holidays = [
        (1, 1, "春节", "新春快乐，万事如意，穿新衣迎新年"),
        (1, 15, "元宵节", "元宵佳节，团团圆圆，甜甜蜜蜜"),
        (5, 5, "端午节", "端午安康，记得吃粽子"),
        (7, 7, "七夕", "七夕快乐，今天的穿搭要浪漫一点"),
        (8, 15, "中秋节", "中秋快乐，月圆人团圆"),
        (9, 9, "重阳节", "重阳登高，秋日穿搭正当时"),
    ]

    result = {}
    for month, day, name, greeting in lunar_holidays:
        try:
            zh = ZhDate(year, month, day)
            solar = zh.to_datetime()
            key = solar.strftime("%m-%d")
            result[key] = {"name": name, "greeting": greeting}
        except Exception:
            continue

    result["04-05"] = {"name": "清明节", "greeting": "清明时节，春暖花开，轻装出行"}
    return result


def get_special_day(date_str: str) -> dict | None:
    """根据日期判断是否为特殊日子。

    Returns:
        {"name": "节日名", "greeting": "祝福语"} 或 None
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    mm_dd = dt.strftime("%m-%d")

    fixed = _load_special_days()
    if mm_dd in fixed:
        return fixed[mm_dd]

    lunar = _lunar_special_days(dt.year)
    if mm_dd in lunar:
        return lunar[mm_dd]

    return None


# ── 笔记内容构建 ──


def build_xhs_content(
    advices: list[ClothingAdvice],
    date_str: str,
) -> tuple[str, str, list[str]]:
    """根据穿搭建议生成小红书笔记的标题、正文和标签。"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = f"{dt.month}/{dt.day}"
    except ValueError:
        dt = None
        date_display = date_str

    city_names = [a.city_name for a in advices]
    city_str = "·".join(city_names)

    special = get_special_day(date_str)

    # 标题（20字限制）
    if special:
        title = f"{special['name']}穿搭 {city_str} 天气指南"
    else:
        title = f"{date_display}穿搭 {city_str} 天气指南"
    if len(title) > 20:
        title = title[:20]

    # 正文
    lines = []
    if special:
        lines.append(f"{special['name']}快乐！{special['greeting']}")
        lines.append("")

    for advice in advices:
        lines.append(f"📍 {advice.city_name} | {advice.weather_desc} {advice.temp_range}")
        lines.append(f"穿衣指数：{advice.clothing_category}")
        lines.append(f"👔 {advice.outfit_suggestion}")
        if advice.extra_tips:
            lines.append("💡 " + "；".join(advice.extra_tips[:2]))
        lines.append("")

    content = "\n".join(lines).rstrip()

    # 标签
    tags = ["穿搭", "天气穿搭", "每日穿搭", "今日穿搭"]
    for name in city_names:
        tags.append(f"{name}穿搭")
    categories = list({a.clothing_category for a in advices})
    for cat in categories:
        tags.append(cat)
    if special:
        tags.append(special["name"])

    return title, content, tags


# ── 发布入口 ──


async def publish_images(
    image_files: list[str],
    advices: list[ClothingAdvice],
    date: str,
) -> bool:
    """穿搭小红书发布入口：构建内容并自动发布。"""
    config = get_xhs_config()
    if not config:
        print("\n⏭ 未配置小红书（跳过发布）")
        return False

    print(f"\n📕 正在发布 {len(image_files)} 张图片到小红书...")

    title, content, tags = build_xhs_content(advices, date_str=date)
    print(f"  标题: {title}")
    print(f"  标签: {', '.join(f'#{t}' for t in tags)}")

    success = await publish_note(
        image_files=image_files,
        title=title,
        content=content,
        tags=tags,
        storage_state_path=config["storage_state_path"],
    )

    if success:
        print("📕 小红书发布完成")
    else:
        print("📕 小红书发布失败，请检查错误截图（output/xhs_error_*.png）")

    return success


async def publish_images_simple(image_files: list[str], date_str: str) -> bool:
    """轻量发布：仅根据文件名构建内容，无需 advices 对象。"""
    config = get_xhs_config()
    if not config:
        print("\n⏭ 未配置小红书（跳过发布）")
        return False

    city_names = []
    for img_path in image_files:
        stem = Path(img_path).stem
        city = stem.split("_")[0] if "_" in stem else stem
        city_names.append(city)

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = f"{dt.month}/{dt.day}"
    except ValueError:
        date_display = date_str

    city_str = "·".join(city_names)
    special = get_special_day(date_str)

    if special:
        title = f"{special['name']}穿搭 {city_str} 天气指南"
    else:
        title = f"{date_display}穿搭 {city_str} 天气指南"
    if len(title) > 20:
        title = title[:20]

    lines = []
    if special:
        lines.append(f"{special['name']}快乐！{special['greeting']}")
        lines.append("")
    lines.append(f"今日穿搭指南 {date_str}")
    for c in city_names:
        lines.append(f"📍 {c}")
    content = "\n".join(lines)

    tags = ["穿搭", "天气穿搭", "每日穿搭", "今日穿搭"]
    if special:
        tags.append(special["name"])

    print(f"\n📕 正在发布 {len(image_files)} 张图片到小红书...")
    print(f"  标题: {title}")

    success = await publish_note(
        image_files=image_files,
        title=title,
        content=content,
        tags=tags,
        storage_state_path=config["storage_state_path"],
    )

    if success:
        print("📕 小红书发布完成")
    else:
        print("📕 小红书发布失败，请检查错误截图（output/xhs_error_*.png）")

    return success
