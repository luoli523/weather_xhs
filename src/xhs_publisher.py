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
    # 发布笔记标签页（默认可能是视频上传，需要先切到图文）
    "publish_note_tab": 'div.creator-tab:has-text("发布笔记"), span:has-text("发布笔记"), a:has-text("发布笔记")',
    # 图片上传 file input（隐藏元素，需用 state="attached"）
    # 图片 input 的 accept 包含 image 格式，与视频 input 区分
    "image_file_input": 'input[type="file"][accept*=".jpg"], input[type="file"][accept*=".png"], input[type="file"][accept*="image"]',
    # 通用 file input 备选（当图片专用选择器找不到时）
    "file_input_any": 'input[type="file"]',
    "upload_area": ".upload-wrapper, .upload-input",
    "image_preview": ".c-image, .img-container, img[src*='upload'], img[src*='spectrum'], .publish-image",
    # 标题输入
    "title_input": '#title-input input, input[placeholder*="标题"], .c-input_inner input',
    # 正文编辑器
    "content_editor": '#post-textarea .ql-editor, div[contenteditable="true"].ql-editor, div[contenteditable="true"]',
    # 发布按钮
    "publish_button": 'button.publishBtn, button.css-k01y1m, button:has-text("发布")',
    # 发布成功标识
    "publish_success": 'text=发布成功, .success-hint, text=已发布',
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
            print("  [1/6] 打开创作中心...")
            await page.goto(CREATOR_PUBLISH_URL, wait_until="networkidle", timeout=30000)
            await _human_delay(2, 3)

            # 检测是否需要登录（跳转到了登录页面）
            current_url = page.url
            if "login" in current_url.lower() or "signin" in current_url.lower():
                print("  ❌ 登录态已过期，请重新运行 python scripts/xhs_login.py")
                await page.screenshot(path="output/xhs_error_login.png")
                return False

            # 保存页面截图供调试
            await page.screenshot(path="output/xhs_debug_page_loaded.png")
            print(f"  当前 URL: {page.url}")

            # ── 2. 切换到「发布笔记」标签页 ──
            # 创作中心默认可能在视频上传页，需要切换到图文笔记
            print("  [2/6] 切换到发布笔记...")
            switched = False
            for tab_selector in [
                'div:has-text("发布笔记")',
                'span:has-text("发布笔记")',
                'a:has-text("发布笔记")',
                'li:has-text("发布笔记")',
            ]:
                try:
                    tab = await page.wait_for_selector(tab_selector, timeout=3000)
                    await tab.click()
                    switched = True
                    print("  ✅ 已切换到发布笔记")
                    await _human_delay(1, 2)
                    break
                except Exception:
                    continue

            if not switched:
                # 可能已经在笔记发布页，继续
                print("  ⚠ 未找到发布笔记标签，尝试继续（可能已在笔记页）")

            await page.screenshot(path="output/xhs_debug_after_tab.png")

            # ── 3. 上传图片 ──
            print(f"  [3/6] 上传 {len(image_files)} 张图片...")
            abs_paths = [str(Path(f).resolve()) for f in image_files]

            # 查找图片专用的 file input（accept 包含图片格式）
            # file input 通常是隐藏的，使用 state="attached" 而非等待可见
            file_input = None

            # 策略 1：查找接受图片格式的 input
            try:
                file_input = await page.wait_for_selector(
                    SELECTORS["image_file_input"], state="attached", timeout=5000
                )
                print("  找到图片上传 input")
            except Exception:
                pass

            # 策略 2：查找所有 file input，排除纯视频的
            if not file_input:
                try:
                    all_inputs = await page.query_selector_all('input[type="file"]')
                    for inp in all_inputs:
                        accept = await inp.get_attribute("accept") or ""
                        # 跳过纯视频 input
                        if accept and all(
                            ext in accept
                            for ext in [".mp4", ".mov"]
                        ) and ".jpg" not in accept and ".png" not in accept:
                            continue
                        file_input = inp
                        accept_display = accept[:60] if accept else "(无限制)"
                        print(f"  找到 file input (accept={accept_display})")
                        break
                except Exception:
                    pass

            # 策略 3：最后兜底 — 取第一个 file input
            if not file_input:
                try:
                    file_input = await page.wait_for_selector(
                        SELECTORS["file_input_any"], state="attached", timeout=5000
                    )
                    accept = await file_input.get_attribute("accept") or "(无限制)"
                    print(f"  兜底: 使用第一个 file input (accept={accept[:60]})")
                except Exception:
                    print("  ❌ 找不到任何文件上传 input")
                    await page.screenshot(path="output/xhs_error_no_input.png")
                    return False

            await file_input.set_input_files(abs_paths)

            # 等待图片上传和处理完成
            await _human_delay(3, 5)
            try:
                await page.wait_for_selector(
                    SELECTORS["image_preview"], timeout=30000
                )
                print("  ✅ 图片上传完成")
            except Exception:
                print("  ⚠ 图片预览检测超时，继续尝试...")

            await page.screenshot(path="output/xhs_debug_after_upload.png")
            await _human_delay(1, 2)

            # ── 4. 填写标题 ──
            print(f"  [4/6] 填写标题: {title}")
            title_filled = False
            for title_selector in [
                SELECTORS["title_input"],
                'input[placeholder*="填写标题"]',
                'input[placeholder*="标题"]',
                '#title-input',
            ]:
                try:
                    title_input = await page.wait_for_selector(
                        title_selector, timeout=3000
                    )
                    await title_input.click()
                    await _human_delay(0.3, 0.6)
                    await title_input.fill(title)
                    title_filled = True
                    break
                except Exception:
                    continue

            if not title_filled:
                print("  ⚠ 无法找到标题输入框，跳过标题")

            await _human_delay(0.5, 1)

            # ── 5. 填写正文和标签 ──
            print("  [5/6] 填写正文...")
            tag_text = " ".join(f"#{t}" for t in tags)
            full_content = f"{content}\n\n{tag_text}"
            content_filled = False

            for editor_selector in [
                SELECTORS["content_editor"],
                'div[contenteditable="true"]',
                '.ql-editor',
            ]:
                try:
                    editor = await page.wait_for_selector(
                        editor_selector, timeout=3000
                    )
                    await editor.click()
                    await _human_delay(0.3, 0.6)
                    await editor.fill(full_content)
                    content_filled = True
                    break
                except Exception:
                    continue

            if not content_filled:
                print("  ❌ 无法找到正文编辑器")
                await page.screenshot(path="output/xhs_error_editor.png")
                return False

            await _human_delay(1, 2)

            # ── 6. 点击发布 ──
            print("  [6/6] 点击发布...")
            await page.screenshot(path="output/xhs_debug_before_publish.png")

            publish_clicked = False
            for btn_selector in [
                SELECTORS["publish_button"],
                'button:has-text("发布")',
                'div.btn:has-text("发布")',
            ]:
                try:
                    publish_btn = await page.wait_for_selector(
                        btn_selector, timeout=3000
                    )
                    await _human_delay(0.5, 1)
                    await publish_btn.click()
                    publish_clicked = True
                    break
                except Exception:
                    continue

            if not publish_clicked:
                print("  ❌ 找不到发布按钮")
                await page.screenshot(path="output/xhs_error_publish_btn.png")
                return False

            # 等待发布结果
            await _human_delay(3, 5)

            # 检查是否发布成功
            current_url = page.url
            await page.screenshot(path="output/xhs_debug_after_publish.png")
            print(f"  发布后 URL: {current_url}")

            # URL 离开了发布页面通常说明发布成功
            if "publish/publish" not in current_url:
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
                print("  ⚠ 发布状态未知，请手动确认（截图已保存到 output/xhs_debug_after_publish.png）")
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


async def publish_images_simple(image_files: list[str], date: str) -> bool:
    """轻量发布：仅根据文件名构建内容，无需 advices 对象。

    适用于 --send-only 模式，直接发布已有图片。
    """
    config = get_xhs_config()
    if not config:
        print("\n⏭ 未配置小红书（跳过发布）")
        return False

    # 从文件名提取城市名（如 "北京_2026-02-13.png" → "北京"）
    city_names = []
    for img_path in image_files:
        stem = Path(img_path).stem
        city = stem.split("_")[0] if "_" in stem else stem
        city_names.append(city)

    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        date_display = f"{dt.month}/{dt.day}"
    except ValueError:
        date_display = date

    city_str = "·".join(city_names)
    title = f"今日穿搭指南 | {city_str} {date_display}"
    if len(title) > 20:
        title = title[:20]

    content = f"今日穿搭指南 {date}\n" + "\n".join(f"📍 {c}" for c in city_names)
    tags = ["穿搭", "天气穿搭", "每日穿搭", "今日穿搭"]

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
