"""小红书自动发布模块

通过 Playwright 浏览器自动化，将穿搭图片发布到小红书。
使用 storage_state 保持登录态，无需每次手动登录。

环境变量：
  XHS_ENABLED            - 是否启用小红书发布（true 启用）
  XHS_STORAGE_STATE_PATH - storage_state.json 路径（默认 ~/.xhs/storage_state.json）
"""

import asyncio
import os
import random
from datetime import datetime
from pathlib import Path

from .clothing_index import ClothingAdvice


# ─── 页面选择器（集中管理，方便后续维护） ───

SELECTORS = {
    # 创作中心页面
    "file_input": 'input[type="file"]',
    "upload_area": ".upload-wrapper",
    "image_preview": ".c-image",
    # 标题输入
    "title_input": '#title-input input, input[placeholder*="标题"], .c-input_inner input',
    # 正文编辑器
    "content_editor": '#post-textarea .ql-editor, div[contenteditable="true"].ql-editor',
    # 发布按钮
    "publish_button": 'button.publishBtn, button.css-k01y1m',
    # 发布成功标识（创作中心 URL 变化或出现成功提示）
    "publish_success": 'text=发布成功, .success-hint',
    # 登录检测
    "login_avatar": ".user-avatar, .user-info, .creator-avatar",
}

# ─── 默认配置 ───

DEFAULT_STORAGE_STATE_PATH = os.path.expanduser("~/.xhs/storage_state.json")
CREATOR_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"


def get_xhs_config() -> dict | None:
    """从环境变量读取小红书配置。

    Returns:
        配置字典 {"storage_state_path": str}，未启用则返回 None。
    """
    enabled = os.getenv("XHS_ENABLED", "").strip().lower()
    if enabled != "true":
        return None

    storage_state_path = os.getenv(
        "XHS_STORAGE_STATE_PATH", DEFAULT_STORAGE_STATE_PATH
    ).strip()

    if not Path(storage_state_path).exists():
        print(f"  ⚠ 小红书 storage_state 文件不存在: {storage_state_path}")
        print("  请先运行 python scripts/xhs_login.py 完成登录")
        return None

    return {"storage_state_path": storage_state_path}


def build_xhs_content(
    advices: list[ClothingAdvice],
    date: str,
) -> tuple[str, str, list[str]]:
    """根据穿搭建议生成小红书笔记的标题、正文和标签。

    Args:
        advices: 各城市穿搭建议列表
        date: 日期字符串（如 2026-02-12）

    Returns:
        (title, content, tags) 三元组
    """
    # 解析日期显示格式
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        date_display = f"{dt.month}/{dt.day}"
    except ValueError:
        date_display = date

    city_names = [a.city_name for a in advices]
    city_str = "·".join(city_names)

    # ── 标题 ──
    title = f"今日穿搭指南 | {city_str} {date_display}"

    # ── 正文 ──
    lines = []
    for advice in advices:
        lines.append(f"📍 {advice.city_name}")
        lines.append(f"🌡 {advice.temp_range}（体感 {advice.feels_like}）")
        lines.append(f"🌤 {advice.weather_desc}")
        lines.append(f"👔 {advice.clothing_category}：{advice.outfit_suggestion}")
        if advice.extra_tips:
            lines.append("💡 " + "；".join(advice.extra_tips[:2]))
        lines.append("")  # 空行分隔城市

    content = "\n".join(lines).rstrip()

    # ── 标签 ──
    tags = ["穿搭", "天气穿搭", "每日穿搭", "今日穿搭"]
    for name in city_names:
        tags.append(f"{name}穿搭")

    return title, content, tags


async def _human_delay(min_sec: float = 0.5, max_sec: float = 2.0):
    """模拟人类操作的随机延迟"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def _slow_type(page, selector: str, text: str):
    """模拟人类打字速度输入文字"""
    element = await page.wait_for_selector(selector, timeout=10000)
    for char in text:
        await element.type(char, delay=random.randint(30, 100))
        if random.random() < 0.1:  # 10% 概率暂停
            await asyncio.sleep(random.uniform(0.2, 0.5))


async def publish_note(
    image_files: list[str],
    title: str,
    content: str,
    tags: list[str],
    storage_state_path: str,
) -> bool:
    """通过 Playwright 自动化发布小红书笔记。

    Args:
        image_files: 要上传的图片文件路径列表
        title: 笔记标题（最长 20 字）
        content: 笔记正文
        tags: 话题标签列表
        storage_state_path: Playwright storage_state.json 路径

    Returns:
        True 发布成功，False 失败
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("  ❌ 未安装 playwright，请先运行：pip install playwright && playwright install chromium")
        return False

    # 截断标题到 20 字（小红书限制）
    if len(title) > 20:
        title = title[:20]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=storage_state_path)
        page = await context.new_page()

        try:
            # ── 1. 打开创作中心发布页 ──
            print("  [1/5] 打开创作中心...")
            await page.goto(CREATOR_PUBLISH_URL, wait_until="networkidle", timeout=30000)
            await _human_delay(1, 2)

            # 检测是否需要登录（跳转到了登录页面）
            current_url = page.url
            if "login" in current_url.lower() or "signin" in current_url.lower():
                print("  ❌ 登录态已过期，请重新运行 python scripts/xhs_login.py")
                await page.screenshot(path="output/xhs_error_login.png")
                return False

            # ── 2. 上传图片 ──
            print(f"  [2/5] 上传 {len(image_files)} 张图片...")
            file_input = await page.wait_for_selector(
                SELECTORS["file_input"], timeout=15000
            )
            # 转为绝对路径
            abs_paths = [str(Path(f).resolve()) for f in image_files]
            await file_input.set_input_files(abs_paths)

            # 等待图片上传和处理完成
            await _human_delay(2, 4)
            # 等待图片预览出现
            try:
                await page.wait_for_selector(
                    SELECTORS["image_preview"], timeout=30000
                )
                print("  ✅ 图片上传完成")
            except Exception:
                print("  ⚠ 图片预览检测超时，继续尝试...")

            await _human_delay(1, 2)

            # ── 3. 填写标题 ──
            print(f"  [3/5] 填写标题: {title}")
            try:
                title_input = await page.wait_for_selector(
                    SELECTORS["title_input"], timeout=10000
                )
                await title_input.click()
                await _human_delay(0.3, 0.6)
                await title_input.fill(title)
            except Exception:
                print("  ⚠ 标题输入框未找到，尝试备选方式...")
                # 备选：通过 placeholder 文本查找
                try:
                    title_alt = await page.wait_for_selector(
                        'input[placeholder*="填写标题"]', timeout=5000
                    )
                    await title_alt.fill(title)
                except Exception:
                    print("  ⚠ 无法找到标题输入框，跳过标题")

            await _human_delay(0.5, 1)

            # ── 4. 填写正文和标签 ──
            print("  [4/5] 填写正文...")
            try:
                editor = await page.wait_for_selector(
                    SELECTORS["content_editor"], timeout=10000
                )
                await editor.click()
                await _human_delay(0.3, 0.6)

                # 拼接正文 + 标签
                tag_text = " ".join(f"#{t}" for t in tags)
                full_content = f"{content}\n\n{tag_text}"
                await editor.fill(full_content)
            except Exception:
                print("  ⚠ 正文编辑器未找到，尝试备选方式...")
                try:
                    editor_alt = await page.wait_for_selector(
                        'div[contenteditable="true"]', timeout=5000
                    )
                    await editor_alt.click()
                    tag_text = " ".join(f"#{t}" for t in tags)
                    full_content = f"{content}\n\n{tag_text}"
                    await editor_alt.fill(full_content)
                except Exception:
                    print("  ❌ 无法找到正文编辑器")
                    await page.screenshot(path="output/xhs_error_editor.png")
                    return False

            await _human_delay(1, 2)

            # ── 5. 点击发布 ──
            print("  [5/5] 点击发布...")
            try:
                publish_btn = await page.wait_for_selector(
                    SELECTORS["publish_button"], timeout=10000
                )
                await _human_delay(0.5, 1)
                await publish_btn.click()
            except Exception:
                # 尝试通过文本查找
                try:
                    publish_btn_alt = await page.wait_for_selector(
                        'button:has-text("发布")', timeout=5000
                    )
                    await publish_btn_alt.click()
                except Exception:
                    print("  ❌ 找不到发布按钮")
                    await page.screenshot(path="output/xhs_error_publish_btn.png")
                    return False

            # 等待发布结果
            await _human_delay(3, 5)

            # 检查是否发布成功（URL 变化或出现提示）
            current_url = page.url
            if "publish" not in current_url.lower() or "success" in current_url.lower():
                print("  ✅ 笔记发布成功！")
                return True

            # 尝试检测成功提示
            try:
                await page.wait_for_selector(
                    SELECTORS["publish_success"], timeout=10000
                )
                print("  ✅ 笔记发布成功！")
                return True
            except Exception:
                print("  ⚠ 发布状态未知，请手动确认")
                await page.screenshot(path="output/xhs_error_publish_result.png")
                return False

        except Exception as e:
            print(f"  ❌ 发布过程出错: {e}")
            try:
                await page.screenshot(path="output/xhs_error_unexpected.png")
            except Exception:
                pass
            return False
        finally:
            await context.close()
            await browser.close()


async def publish_images(
    image_files: list[str],
    advices: list[ClothingAdvice],
    date: str,
) -> bool:
    """小红书发布入口：构建内容并自动发布。

    Args:
        image_files: 图片文件路径列表
        advices: 各城市穿搭建议
        date: 日期字符串

    Returns:
        True 发布成功，False 失败或未启用
    """
    config = get_xhs_config()
    if not config:
        print("\n⏭ 未配置小红书（跳过发布）")
        return False

    print(f"\n📕 正在发布 {len(image_files)} 张图片到小红书...")

    title, content, tags = build_xhs_content(advices, date)
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
