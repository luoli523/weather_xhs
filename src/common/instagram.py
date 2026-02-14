"""Instagram 共享基础功能

使用 instagrapi 库实现 Instagram 发布，支持单图和相册。

认证策略（与小红书 storage_state 类似）：
  1. 本地运行 scripts/ig_login.py 完成首次登录（含 Challenge 验证）
  2. session 保存到 ~/.instagram/session.json
  3. 后续运行优先加载 session，不触发 Challenge
  4. CI 环境通过 GitHub Secret IG_SESSION（base64）恢复 session 文件

环境变量：
  IG_ENABLED       - 是否启用 Instagram 发布（true 启用）
  IG_USERNAME      - Instagram 用户名（session 有效时可选）
  IG_PASSWORD      - Instagram 密码（session 有效时可选）
  IG_SESSION_PATH  - session 文件路径（默认 ~/.instagram/session.json）
"""

import os
import time
from pathlib import Path

# ─── 发布频率控制 ───

IG_PUBLISH_INTERVAL = 60  # 秒
_last_publish_time: float = 0

# ─── 默认配置 ───

DEFAULT_SESSION_PATH = os.path.expanduser("~/.instagram/session.json")

# 设备信息：使用较新的 Instagram App 版本，避免 unsupported_version 错误
DEVICE_SETTINGS = {
    "app_version": "357.0.0.0.62",
    "android_version": 34,
    "android_release": "14.0",
    "dpi": "440dpi",
    "resolution": "1080x2400",
    "manufacturer": "Google",
    "device": "husky",
    "model": "Pixel 8 Pro",
    "cpu": "tensor",
    "version_code": "604247854",
}
USER_AGENT = (
    "Instagram 357.0.0.0.62 Android (34/14.0; 440dpi; 1080x2400; "
    "Google; Pixel 8 Pro; husky; tensor; en_US; 604247854)"
)


def _new_client():
    """创建配置好设备信息的 instagrapi Client。"""
    from instagrapi import Client

    cl = Client()
    cl.set_device(DEVICE_SETTINGS)
    cl.set_user_agent(USER_AGENT)
    cl.delay_range = [1, 3]
    return cl


def get_ig_config() -> dict | None:
    """从环境变量读取 Instagram 配置。

    优先检查 session 文件是否存在；如果 session 存在，
    用户名和密码是可选的（session 内已包含认证信息）。

    Returns:
        配置字典 {"username", "password", "session_path"}，未启用则返回 None。
    """
    enabled = os.getenv("IG_ENABLED", "").strip().lower()
    if enabled != "true":
        return None

    session_path = os.getenv(
        "IG_SESSION_PATH", DEFAULT_SESSION_PATH
    ).strip()

    username = os.getenv("IG_USERNAME", "").strip()
    password = os.getenv("IG_PASSWORD", "").strip()

    # session 文件存在时，账密可选
    if not Path(session_path).exists():
        if not username or not password:
            print("  ⚠ Instagram session 文件不存在，且 IG_USERNAME / IG_PASSWORD 未设置")
            print("  请先运行 python scripts/ig_login.py 完成登录")
            return None

    return {
        "username": username,
        "password": password,
        "session_path": session_path,
    }


def _get_client(config: dict):
    """创建并登录 instagrapi Client，优先加载已有 session。

    登录优先级：
      1. 加载 session 文件 → 复用已有会话（不触发 Challenge）
      2. session 无效时，用账密重新登录（可能触发 Challenge）
      3. 触发 Challenge 则提示用户在本地运行 ig_login.py

    session 文件包含 device_id / phone_id / uuid 等设备指纹，
    Instagram 据此判断是否为"已知设备"，跳过 Challenge 验证。
    """
    try:
        from instagrapi import Client  # noqa: F401
    except ImportError:
        print("  ❌ 未安装 instagrapi，请先运行：pip install instagrapi")
        return None

    session_path = config["session_path"]

    # ── 策略 1：加载已有 session ──
    if Path(session_path).exists():
        cl = _new_client()
        try:
            cl.load_settings(session_path)
            cl.login(config["username"], config["password"])
            # 验证 session 是否有效
            try:
                cl.get_timeline_feed()
            except Exception:
                # timeline 可能偶尔失败，尝试更轻量的验证
                cl.account_info()
            print("  ✅ Instagram 已通过 session 登录")
            # 刷新 session（延长有效期）
            cl.dump_settings(session_path)
            return cl
        except Exception as e:
            print(f"  ⚠ Session 加载失败: {e}")
            print("  尝试仅凭 session 设备指纹重新登录...")

            # 策略 1b：保留设备指纹但重新登录
            if config["username"] and config["password"]:
                try:
                    cl2 = _new_client()
                    old_settings = cl.get_settings()
                    cl2.set_settings(old_settings)
                    cl2.set_uuids(old_settings)
                    cl2.login(config["username"], config["password"])
                    cl2.dump_settings(session_path)
                    print("  ✅ Instagram 使用设备指纹重新登录成功")
                    return cl2
                except Exception as e2:
                    print(f"  ⚠ 设备指纹重新登录也失败: {e2}")

    # ── 策略 2：无 session，纯账密登录 ──
    if not config["username"] or not config["password"]:
        print("  ❌ 无可用 session，且未提供账密")
        print("     请先运行: python scripts/ig_login.py")
        return None

    try:
        cl_new = _new_client()
        cl_new.login(config["username"], config["password"])
        Path(session_path).parent.mkdir(parents=True, exist_ok=True)
        cl_new.dump_settings(session_path)
        print("  ✅ Instagram 登录成功，session 已保存")
        return cl_new
    except Exception as e:
        print(f"  ❌ Instagram 登录失败: {e}")
        print("     可能是触发了 Challenge（安全验证），请在本地运行：")
        print("     python scripts/ig_login.py")
        return None


async def _wait_for_rate_limit():
    """检查距离上次发布是否已过间隔时间，不足则等待。"""
    import asyncio
    global _last_publish_time
    if _last_publish_time == 0:
        return
    elapsed = time.time() - _last_publish_time
    if elapsed < IG_PUBLISH_INTERVAL:
        wait_sec = IG_PUBLISH_INTERVAL - elapsed
        print(f"  ⏳ 距上次 IG 发布仅 {elapsed:.0f}s，等待 {wait_sec:.0f}s 后继续...")
        await asyncio.sleep(wait_sec)


def _ensure_jpg(image_files: list[str]) -> tuple[list[Path], list[Path]]:
    """确保所有图片为 JPG 格式（Instagram 相册不支持 PNG）。

    Returns:
        (jpg_paths, temp_files) — 转换后的路径列表 + 需要清理的临时文件列表
    """
    from PIL import Image

    jpg_paths = []
    temp_files = []

    for f in image_files:
        p = Path(f)
        if p.suffix.lower() in (".jpg", ".jpeg"):
            jpg_paths.append(p)
        else:
            jpg_path = p.with_suffix(".jpg")
            img = Image.open(p)
            img = img.convert("RGB")
            img.save(jpg_path, "JPEG", quality=95)
            jpg_paths.append(jpg_path)
            temp_files.append(jpg_path)

    return jpg_paths, temp_files


async def publish_album(
    image_files: list[str],
    caption: str,
    config: dict,
) -> bool:
    """发布多图相册到 Instagram。

    自动将 PNG 转换为 JPG（Instagram 相册要求 JPG 格式），
    上传完成后清理临时文件。

    Args:
        image_files: 图片文件路径列表
        caption: 帖子文案（含 #hashtags）
        config: Instagram 配置字典

    Returns:
        True 发布成功，False 失败
    """
    global _last_publish_time

    await _wait_for_rate_limit()

    cl = _get_client(config)
    if not cl:
        return False

    jpg_paths, temp_files = _ensure_jpg(image_files)

    try:
        if len(jpg_paths) == 1:
            media = cl.photo_upload(jpg_paths[0], caption)
        else:
            media = cl.album_upload(jpg_paths, caption)

        if media and media.pk:
            _last_publish_time = time.time()
            print(f"  ✅ Instagram 发布成功: https://www.instagram.com/p/{media.code}/")
            return True
        else:
            print("  ❌ Instagram 发布失败：未返回 media 信息")
            return False
    except Exception as e:
        print(f"  ❌ Instagram 发布出错: {e}")
        return False
    finally:
        # 清理临时 JPG 文件
        for tmp in temp_files:
            try:
                tmp.unlink()
            except Exception:
                pass
