"""穿搭 Instagram 内容构建与发布

构建穿搭帖子的文案（含特殊日子祝福、hashtags），
并调用 common.instagram.publish_album() 完成发布。
"""

from datetime import datetime
from pathlib import Path

from src.common.instagram import get_ig_config, publish_album
from .xhs import get_special_day  # 复用特殊日子检测逻辑


# ── 帖子内容构建 ──


def build_ig_caption(
    advices: list,
    date_str: str,
) -> str:
    """根据穿搭建议生成 Instagram 帖子文案。

    Instagram 不分标题和正文，所有内容放在 caption 中，
    hashtags 直接追加在文案末尾。
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = f"{dt.month}/{dt.day}"
    except ValueError:
        date_display = date_str

    city_names = [a.city_name for a in advices]
    special = get_special_day(date_str)

    lines = []

    # 标题行
    if special:
        lines.append(f"🎉 {special['name']}快乐！{special['greeting']}")
        lines.append("")

    lines.append(f"📅 {date_display} 今日穿搭指南")
    lines.append("")

    # 各城市穿搭信息
    for advice in advices:
        lines.append(f"📍 {advice.city_name} | {advice.weather_desc} {advice.temp_range}")
        lines.append(f"穿衣指数：{advice.clothing_category}")
        lines.append(f"👔 {advice.outfit_suggestion}")
        if advice.extra_tips:
            lines.append("💡 " + "；".join(advice.extra_tips[:2]))
        lines.append("")

    # Hashtags
    tags = ["#穿搭", "#OOTD", "#每日穿搭", "#天气穿搭", "#穿搭分享"]
    for name in city_names:
        tags.append(f"#{name}穿搭")
    categories = list({a.clothing_category for a in advices})
    for cat in categories:
        tags.append(f"#{cat}")
    if special:
        tags.append(f"#{special['name']}")

    lines.append(" ".join(tags))

    return "\n".join(lines).rstrip()


# ── 发布入口 ──


async def publish_images(
    image_files: list[str],
    advices: list,
    date: str,
) -> bool:
    """穿搭 Instagram 发布入口：构建 caption 并自动发布。"""
    config = get_ig_config()
    if not config:
        print("\n⏭ 未配置 Instagram（跳过发布）")
        return False

    print(f"\n📷 正在发布 {len(image_files)} 张图片到 Instagram...")

    caption = build_ig_caption(advices, date_str=date)
    # 显示前几行
    preview_lines = caption.split("\n")[:3]
    for line in preview_lines:
        print(f"  {line}")
    print("  ...")

    success = await publish_album(
        image_files=image_files,
        caption=caption,
        config=config,
    )

    if success:
        print("📷 Instagram 发布完成")
    else:
        print("📷 Instagram 发布失败")

    return success


async def publish_images_simple(image_files: list[str], date_str: str) -> bool:
    """轻量发布：仅根据文件名构建内容，无需 advices 对象。

    适用于 --send-ig 模式，直接发送已有图片。
    """
    config = get_ig_config()
    if not config:
        print("\n⏭ 未配置 Instagram（跳过发布）")
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

    special = get_special_day(date_str)

    lines = []
    if special:
        lines.append(f"🎉 {special['name']}快乐！{special['greeting']}")
        lines.append("")

    lines.append(f"📅 {date_display} 今日穿搭指南")
    lines.append("")
    for c in city_names:
        lines.append(f"📍 {c}")
    lines.append("")

    tags = ["#穿搭", "#OOTD", "#每日穿搭", "#天气穿搭"]
    if special:
        tags.append(f"#{special['name']}")
    lines.append(" ".join(tags))

    caption = "\n".join(lines).rstrip()

    print(f"\n📷 正在发布 {len(image_files)} 张图片到 Instagram...")

    success = await publish_album(
        image_files=image_files,
        caption=caption,
        config=config,
    )

    if success:
        print("📷 Instagram 发布完成")
    else:
        print("📷 Instagram 发布失败")

    return success
