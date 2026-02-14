"""小红书共享基础功能

提供配置读取和笔记发布自动化（Playwright），
供 clothing 和 solar_term 模块复用。

环境变量：
  XHS_ENABLED            - 是否启用小红书发布（true 启用）
  XHS_STORAGE_STATE_PATH - storage_state.json 路径（默认 ~/.xhs/storage_state.json）
"""

import asyncio
import os
import random
from pathlib import Path


# ─── 页面选择器（集中管理，方便后续维护） ───

SELECTORS = {
    "publish_note_btn": '//*[text()="发布笔记"]',
    "upload_image_btn": '//*[text()="上传图文"]',
    "file_input": 'input[type="file"]',
    "image_preview": ".c-image, .img-container, img[src*='spectrum'], .publish-image, .images-area img",
    "title_input": '//*[@placeholder="填写标题，可能会有更多赞哦～"]',
    "title_input_alt": 'input[placeholder*="标题"]',
    "content_editor": '//*[@placeholder="填写更全面的描述信息，让更多的人看到你吧！"]',
    "content_editor_alt": 'div[contenteditable="true"]',
    "topic_item": ".publish-topic-item",
    "publish_button": '//*[text()="发布"]',
    "publish_button_alt": 'button:has-text("发布")',
    "publish_success": 'text=发布成功, .success-hint, text=已发布',
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


async def _human_delay(min_sec: float = 0.5, max_sec: float = 2.0):
    """模拟人类操作的随机延迟"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def _slow_type(page, selector: str, text: str):
    """模拟人类打字速度输入文字"""
    element = await page.wait_for_selector(selector, timeout=10000)
    for char in text:
        await element.type(char, delay=random.randint(30, 100))
        if random.random() < 0.1:
            await asyncio.sleep(random.uniform(0.2, 0.5))


async def _click_by_text(page, text: str, timeout: int = 5000) -> bool:
    """通过精确文本匹配点击元素"""
    try:
        el = await page.wait_for_selector(f'//*[text()="{text}"]', timeout=timeout)
        await el.click()
        return True
    except Exception:
        pass
    try:
        el = await page.wait_for_selector(f'text="{text}"', timeout=timeout // 2)
        await el.click()
        return True
    except Exception:
        pass
    return False


async def publish_note(
    image_files: list[str],
    title: str,
    content: str,
    tags: list[str],
    storage_state_path: str,
) -> bool:
    """通过 Playwright 自动化发布小红书图文笔记。

    页面结构（基于实际截图确认）：
      - 顶部有三个标签页：「上传视频」(默认) | 「上传图文」| 「写长文」
      - 左侧「发布笔记」是下拉菜单按钮（不要点它）
      - 需要直接点击顶部「上传图文」标签切换到图文模式

    流程：打开发布页 → 点击顶部「上传图文」标签
      → 逐张上传图片 → 填标题 → 填正文+标签 → 点击发布

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

    if len(title) > 20:
        title = title[:20]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=storage_state_path)
        page = await context.new_page()
        page.set_default_timeout(15000)

        try:
            # ── 1. 打开创作中心发布页 ──
            print("  [1/6] 打开创作中心...")
            await page.goto(CREATOR_PUBLISH_URL, wait_until="networkidle", timeout=30000)
            await _human_delay(2, 3)

            current_url = page.url
            if "login" in current_url.lower() or "signin" in current_url.lower():
                print("  ❌ 登录态已过期，请重新运行 python scripts/xhs_login.py")
                await page.screenshot(path="output/xhs_error_login.png")
                return False

            await page.screenshot(path="output/xhs_debug_1_page_loaded.png")
            print(f"  当前 URL: {page.url}")

            # ── 2. 点击顶部「上传图文」标签 ──
            print("  [2/6] 切换到「上传图文」标签...")
            switched = await page.evaluate("""() => {
                const elements = document.querySelectorAll('*');
                for (const el of elements) {
                    if (el.textContent.trim() === '上传图文' && el.children.length === 0) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""")

            if not switched:
                print("  ❌ 无法切换到上传图文标签")
                await page.screenshot(path="output/xhs_error_no_tab.png")
                return False

            print("  ✅ 已切换到上传图文")
            await _human_delay(1, 2)
            await page.screenshot(path="output/xhs_debug_2_after_tab.png")

            # ── 3. 逐张上传图片 ──
            print(f"  [3/6] 上传 {len(image_files)} 张图片...")
            abs_paths = [str(Path(f).resolve()) for f in image_files]

            for i, img_path in enumerate(abs_paths):
                file_input = await page.wait_for_selector(
                    SELECTORS["file_input"], state="attached", timeout=10000
                )
                await file_input.set_input_files(img_path)
                print(f"    [{i+1}/{len(abs_paths)}] 已提交: {Path(img_path).name}")
                await _human_delay(2, 4)

            await _human_delay(3, 5)
            try:
                await page.wait_for_selector(
                    SELECTORS["image_preview"], timeout=30000
                )
                print("  ✅ 图片上传完成")
            except Exception:
                print("  ⚠ 图片预览检测超时，继续尝试...")

            await page.screenshot(path="output/xhs_debug_3_after_upload.png")
            await _human_delay(1, 2)

            # ── 4. 填写标题 ──
            print(f"  [4/6] 填写标题: {title}")
            title_filled = False
            for sel in [SELECTORS["title_input"], SELECTORS["title_input_alt"]]:
                try:
                    el = await page.wait_for_selector(sel, timeout=5000)
                    await el.click()
                    await _human_delay(0.3, 0.5)
                    await el.fill(title)
                    title_filled = True
                    break
                except Exception:
                    continue

            if not title_filled:
                print("  ⚠ 无法找到标题输入框，跳过标题")

            await _human_delay(0.5, 1)

            # ── 5. 填写正文 + 话题标签 ──
            print("  [5/6] 填写正文...")
            content_filled = False
            for sel in [SELECTORS["content_editor"], SELECTORS["content_editor_alt"]]:
                try:
                    editor = await page.wait_for_selector(sel, timeout=5000)
                    await editor.click()
                    await _human_delay(0.3, 0.5)

                    await editor.fill(content)
                    await _human_delay(0.5, 1)

                    for tag in tags:
                        tag_with_hash = f"#{tag}"
                        await editor.type(f" {tag_with_hash}")
                        await _human_delay(0.8, 1.5)
                        try:
                            topic_items = await page.query_selector_all(
                                SELECTORS["topic_item"]
                            )
                            for item in topic_items:
                                item_text = await item.inner_text()
                                if tag in item_text:
                                    await item.click()
                                    print(f"    标签已选: {tag_with_hash}")
                                    break
                        except Exception:
                            pass
                        await _human_delay(0.3, 0.6)

                    content_filled = True
                    break
                except Exception:
                    continue

            if not content_filled:
                print("  ❌ 无法找到正文编辑器")
                await page.screenshot(path="output/xhs_error_editor.png")
                return False

            await page.screenshot(path="output/xhs_debug_5_before_publish.png")
            await _human_delay(1, 2)

            # ── 6. 点击发布 ──
            print("  [6/6] 点击发布...")
            publish_clicked = False
            for sel in [SELECTORS["publish_button"], SELECTORS["publish_button_alt"]]:
                try:
                    btn = await page.wait_for_selector(sel, timeout=5000)
                    await _human_delay(0.5, 1)
                    await btn.click()
                    publish_clicked = True
                    break
                except Exception:
                    continue

            if not publish_clicked:
                print("  ❌ 找不到发布按钮")
                await page.screenshot(path="output/xhs_error_publish_btn.png")
                return False

            await _human_delay(3, 5)
            current_url = page.url
            await page.screenshot(path="output/xhs_debug_6_after_publish.png")
            print(f"  发布后 URL: {current_url}")

            if "publish/publish" not in current_url:
                print("  ✅ 笔记发布成功！")
                return True

            try:
                await page.wait_for_selector(
                    SELECTORS["publish_success"], timeout=10000
                )
                print("  ✅ 笔记发布成功！")
                return True
            except Exception:
                print("  ⚠ 发布状态未知，请检查截图 output/xhs_debug_6_after_publish.png")
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
