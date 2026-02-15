"""Telegram 共享基础功能

提供配置读取、单张图片发送和多图相册发送，供 clothing 和 solar_term 模块复用。

环境变量：
  TELEGRAM_BOT_TOKEN  - Bot Token（从 @BotFather 获取）
  TELEGRAM_CHAT_ID    - 接收消息的 chat_id
"""

import json
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


async def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
) -> bool:
    """发送纯文本消息到 Telegram

    Returns:
        True 发送成功，False 发送失败
    """
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )

    if resp.status_code == 200 and resp.json().get("ok"):
        return True
    else:
        print(f"    ⚠ Telegram 消息发送失败: {resp.status_code} {resp.text[:200]}")
        return False


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


async def send_media_group(
    bot_token: str,
    chat_id: str,
    photos: list[dict],
) -> bool:
    """以相册形式一次发送多张图片到 Telegram（2-10 张）。

    Args:
        bot_token: Bot Token
        chat_id: 目标 chat_id
        photos: 图片列表，每项为 {"path": str, "caption": str}
                caption 可选，每张图各自的说明文字（滑动查看时显示）

    Returns:
        True 发送成功，False 发送失败
    """
    if not photos:
        return False
    # Telegram 限制：相册 2-10 张，单张走 sendPhoto
    if len(photos) == 1:
        return await send_photo(
            bot_token, chat_id, photos[0]["path"], photos[0].get("caption", "")
        )

    url = f"{TELEGRAM_API}/bot{bot_token}/sendMediaGroup"

    media = []
    files = {}
    file_handles = []

    try:
        for i, photo in enumerate(photos):
            attach_name = f"photo{i}"
            media_item = {
                "type": "photo",
                "media": f"attach://{attach_name}",
            }
            if photo.get("caption"):
                media_item["caption"] = photo["caption"]
                media_item["parse_mode"] = "HTML"
            media.append(media_item)

            file_path = Path(photo["path"])
            fh = open(file_path, "rb")
            file_handles.append(fh)
            files[attach_name] = (file_path.name, fh, "image/png")

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                data={"chat_id": chat_id, "media": json.dumps(media)},
                files=files,
            )

        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        else:
            print(f"    ⚠ Telegram 相册发送失败: {resp.status_code} {resp.text[:200]}")
            return False
    finally:
        for fh in file_handles:
            fh.close()
