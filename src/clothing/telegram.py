"""穿搭 Telegram 推送

以相册形式一条消息发送所有穿搭图片到 Telegram。
每张图各自附带城市天气穿搭 caption，滑动查看时显示。
"""

from pathlib import Path

from src.common.telegram import get_telegram_config, send_media_group, send_message
from src.clothing.instagram import build_ig_caption


async def send_images(
    image_files: list[str],
    advices: list,
    date: str,
) -> int:
    """以相册形式发送穿搭图片到 Telegram，并附带完整文案。

    先发送图片相册，再单独发送一条完整文案消息（与 IG 一致），方便直接复制。

    Args:
        image_files: 图片文件路径列表
        advices: ClothingAdvice 列表（与 image_files 一一对应）
        date: 日期字符串

    Returns:
        成功发送的图片数量（全部成功或全部失败）
    """
    config = get_telegram_config()
    if not config:
        print("\n⏭ 未配置 Telegram（跳过推送）")
        return 0

    bot_token, chat_id = config
    print(f"\n📱 正在推送 {len(image_files)} 张穿搭图到 Telegram（相册模式）...")

    photos = []
    for img_path, advice in zip(image_files, advices):
        photos.append({"path": img_path, "caption": ""})
        print(f"  📷 {advice.city_name}")

    ok = await send_media_group(bot_token, chat_id, photos)
    if ok:
        count = len(image_files)
        print(f"📱 Telegram 推送完成：{count} 张（相册）")
        full_caption = build_ig_caption(advices, date_str=date)
        await send_message(bot_token, chat_id, full_caption, parse_mode="")
        print(f"📱 Telegram 完整文案已发送")
        return count
    else:
        print("📱 Telegram 推送失败")
        return 0


async def send_images_simple(image_files: list[str], date: str) -> int:
    """轻量发送：以相册形式发送，caption 从文件名构建。

    适用于 --send-telegram 模式，直接发送已有图片。
    """
    config = get_telegram_config()
    if not config:
        print("\n❌ Telegram 未启用或未配置，无法发送")
        return 0

    bot_token, chat_id = config
    print(f"\n📱 正在推送 {len(image_files)} 张图片到 Telegram（相册模式）...")

    photos = []
    for img_path in image_files:
        file_name = Path(img_path).stem
        city_name = file_name.split("_")[0] if "_" in file_name else file_name
        caption = f"<b>{city_name} {date} 穿搭指南</b>"
        photos.append({"path": img_path, "caption": caption})
        print(f"  📷 {city_name}")

    ok = await send_media_group(bot_token, chat_id, photos)
    if ok:
        count = len(image_files)
        print(f"📱 Telegram 推送完成：{count} 张（相册）")
        return count
    else:
        print("📱 Telegram 推送失败")
        return 0
