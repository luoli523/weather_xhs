"""Telegram 消息推送模块

通过 Telegram Bot API 发送穿搭图片到指定聊天。
使用项目已有的 httpx，无需额外依赖。

环境变量：
  TELEGRAM_BOT_TOKEN  - Bot Token（从 @BotFather 获取）
  TELEGRAM_CHAT_ID    - 接收消息的 chat_id（个人/群组/频道均可）
"""

import os
from pathlib import Path

import httpx


TELEGRAM_API = "https://api.telegram.org"


def get_telegram_config() -> tuple[str, str] | None:
    """从环境变量读取 Telegram 配置，未启用或未配置则返回 None"""
    enabled = os.getenv("TELEGRAM_ENABLED", "").strip().lower()
    if enabled != "true":
        return None
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        return None
    return bot_token, chat_id


async def send_photo(
    bot_token: str,
    chat_id: str,
    photo_path: str,
    caption: str = "",
) -> bool:
    """发送单张图片到 Telegram

    Returns:
        True 发送成功，False 发送失败
    """
    url = f"{TELEGRAM_API}/bot{bot_token}/sendPhoto"
    file_path = Path(photo_path)

    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, "rb") as f:
            resp = await client.post(
                url,
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": (file_path.name, f, "image/png")},
            )

        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        else:
            print(f"    ⚠ Telegram 发送失败: {resp.status_code} {resp.text[:200]}")
            return False


async def send_images(
    image_files: list[str],
    advices: list,
    date: str,
) -> int:
    """批量发送穿搭图片到 Telegram

    Args:
        image_files: 图片文件路径列表
        advices: ClothingAdvice 列表（与 image_files 一一对应）
        date: 日期字符串

    Returns:
        成功发送的图片数量
    """
    config = get_telegram_config()
    if not config:
        print("\n⏭ 未配置 Telegram（跳过推送）")
        return 0

    bot_token, chat_id = config
    print(f"\n📱 正在推送 {len(image_files)} 张图片到 Telegram...")

    sent_count = 0
    for img_path, advice in zip(image_files, advices):
        caption = (
            f"<b>{advice.city_name} {date} 穿搭指南</b>\n"
            f"🌡 {advice.temp_range}（体感 {advice.feels_like}）\n"
            f"🌤 {advice.weather_desc}\n"
            f"👔 {advice.clothing_category}：{advice.outfit_suggestion}"
        )
        print(f"  发送 {advice.city_name}...")
        ok = await send_photo(bot_token, chat_id, img_path, caption=caption)
        if ok:
            sent_count += 1
            print(f"  ✅ {advice.city_name} 已发送")

    print(f"📱 Telegram 推送完成：{sent_count}/{len(image_files)} 张")
    return sent_count


async def send_images_simple(image_files: list[str], date: str) -> int:
    """轻量发送：仅根据文件名构建 caption，无需 advices 对象。

    适用于 --send-only 模式，直接发送已有图片。
    """
    config = get_telegram_config()
    if not config:
        print("\n❌ Telegram 未启用或未配置，无法发送")
        return 0

    bot_token, chat_id = config
    print(f"\n📱 正在推送 {len(image_files)} 张图片到 Telegram...")

    sent_count = 0
    for img_path in image_files:
        file_name = Path(img_path).stem  # e.g. "北京_2026-02-13"
        city_name = file_name.split("_")[0] if "_" in file_name else file_name
        caption = f"<b>{city_name} {date} 穿搭指南</b>"
        print(f"  发送 {city_name}...")
        ok = await send_photo(bot_token, chat_id, img_path, caption=caption)
        if ok:
            sent_count += 1
            print(f"  ✅ {city_name} 已发送")

    print(f"📱 Telegram 推送完成：{sent_count}/{len(image_files)} 张")
    return sent_count
