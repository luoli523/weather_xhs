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
from datetime import datetime, date
from pathlib import Path

import yaml

from .clothing_index import ClothingAdvice


# ─── 页面选择器（集中管理，方便后续维护） ───

SELECTORS = {
    # 步骤 1：点击"发布笔记"从视频页切换到笔记发布
    "publish_note_btn": '//*[text()="发布笔记"]',
    # 步骤 2：点击"上传图文"切换到图片上传模式
    "upload_image_btn": '//*[text()="上传图文"]',
    # 步骤 3：图片 file input（隐藏元素，逐个上传）
    "file_input": 'input[type="file"]',
    # 图片预览（判断上传是否完成）
    "image_preview": ".c-image, .img-container, img[src*='spectrum'], .publish-image, .images-area img",
    # 标题输入（小红书特定 placeholder）
    "title_input": '//*[@placeholder="填写标题，可能会有更多赞哦～"]',
    "title_input_alt": 'input[placeholder*="标题"]',
    # 正文编辑器
    "content_editor": '//*[@placeholder="填写更全面的描述信息，让更多的人看到你吧！"]',
    "content_editor_alt": 'div[contenteditable="true"]',
    # 话题标签候选列表项
    "topic_item": ".publish-topic-item",
    # 发布按钮
    "publish_button": '//*[text()="发布"]',
    "publish_button_alt": 'button:has-text("发布")',
    # 发布成功标识
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


def _load_special_days(config_path: str = "config/special_days.yaml") -> dict:
    """加载固定日期节日配置"""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("fixed", {})
    except FileNotFoundError:
        return {}


def _lunar_special_days(year: int) -> dict[str, dict]:
    """计算农历节日对应的公历日期（每年不同）。

    返回 {"MM-DD": {"name": ..., "greeting": ...}} 格式，与 fixed 配置统一。
    """
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

    # 清明节：固定在公历 4 月 4 日或 5 日，简化为 4-05
    result["04-05"] = {"name": "清明节", "greeting": "清明时节，春暖花开，轻装出行"}

    return result


def get_special_day(date_str: str) -> dict | None:
    """根据日期判断是否为特殊日子。

    Args:
        date_str: 日期字符串（YYYY-MM-DD）

    Returns:
        {"name": "节日名", "greeting": "祝福语"} 或 None
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None

    mm_dd = dt.strftime("%m-%d")

    # 1. 查固定日期节日
    fixed = _load_special_days()
    if mm_dd in fixed:
        return fixed[mm_dd]

    # 2. 查农历节日
    lunar = _lunar_special_days(dt.year)
    if mm_dd in lunar:
        return lunar[mm_dd]

    return None


def build_xhs_content(
    advices: list[ClothingAdvice],
    date_str: str,
) -> tuple[str, str, list[str]]:
    """根据穿搭建议生成小红书笔记的标题、正文和标签。

    Args:
        advices: 各城市穿搭建议列表
        date_str: 日期字符串（如 2026-02-12）

    Returns:
        (title, content, tags) 三元组
    """
    # 解析日期
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = f"{dt.month}/{dt.day}"
    except ValueError:
        dt = None
        date_display = date_str

    city_names = [a.city_name for a in advices]
    city_str = "·".join(city_names)

    # 检查是否为特殊日子
    special = get_special_day(date_str)

    # ── 标题（20字限制）──
    if special:
        title = f"{special['name']}穿搭 {city_str} 天气指南"
    else:
        title = f"{date_display}穿搭 {city_str} 天气指南"
    if len(title) > 20:
        title = title[:20]

    # ── 正文 ──
    lines = []

    # 特殊日子祝福语开头
    if special:
        lines.append(f"{special['name']}快乐！{special['greeting']}")
        lines.append("")

    for advice in advices:
        # 城市行：城市 | 天气 温度
        lines.append(f"📍 {advice.city_name} | {advice.weather_desc} {advice.temp_range}")
        lines.append(f"穿衣指数：{advice.clothing_category}")
        lines.append(f"👔 {advice.outfit_suggestion}")
        if advice.extra_tips:
            lines.append("💡 " + "；".join(advice.extra_tips[:2]))
        lines.append("")

    content = "\n".join(lines).rstrip()

    # ── 标签 ──
    tags = ["穿搭", "天气穿搭", "每日穿搭", "今日穿搭"]
    for name in city_names:
        tags.append(f"{name}穿搭")
    # 天气相关标签
    categories = list({a.clothing_category for a in advices})
    for cat in categories:
        tags.append(cat)
    # 节日标签
    if special:
        tags.append(special["name"])

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


async def _click_by_text(page, text: str, timeout: int = 5000) -> bool:
    """通过精确文本匹配点击元素，尝试 XPath 和 CSS 两种方式。"""
    # XPath 精确文本匹配
    try:
        el = await page.wait_for_selector(f'//*[text()="{text}"]', timeout=timeout)
        await el.click()
        return True
    except Exception:
        pass
    # CSS :has-text（可能匹配更宽泛）
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

    # 截断标题到 20 字（小红书限制）
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

            # 检测是否需要登录
            current_url = page.url
            if "login" in current_url.lower() or "signin" in current_url.lower():
                print("  ❌ 登录态已过期，请重新运行 python scripts/xhs_login.py")
                await page.screenshot(path="output/xhs_error_login.png")
                return False

            await page.screenshot(path="output/xhs_debug_1_page_loaded.png")
            print(f"  当前 URL: {page.url}")

            # ── 2. 点击顶部「上传图文」标签 ──
            # 页面顶部有三个标签：上传视频(默认) | 上传图文 | 写长文
            # 注意：不要点左侧的「发布笔记」按钮（那是下拉菜单）
            # 注意：标签元素可能在视口之外，Playwright 常规 click 会超时，
            #       因此使用 JavaScript evaluate 直接点击（绕过视口检查）。
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
                # 每次上传前重新获取 file input（上传后 DOM 可能刷新）
                file_input = await page.wait_for_selector(
                    SELECTORS["file_input"], state="attached", timeout=10000
                )
                await file_input.set_input_files(img_path)
                print(f"    [{i+1}/{len(abs_paths)}] 已提交: {Path(img_path).name}")
                await _human_delay(2, 4)

            # 等待所有图片处理完成
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

                    # 先输入正文
                    await editor.fill(content)
                    await _human_delay(0.5, 1)

                    # 逐个输入话题标签（输入后从候选列表中点击确认）
                    for tag in tags:
                        tag_with_hash = f"#{tag}"
                        await editor.type(f" {tag_with_hash}")
                        await _human_delay(0.8, 1.5)
                        # 尝试从话题候选列表点击匹配项
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
                            pass  # 候选列表未出现，标签仍会作为文本保留
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

            # 等待发布结果
            await _human_delay(3, 5)
            current_url = page.url
            await page.screenshot(path="output/xhs_debug_6_after_publish.png")
            print(f"  发布后 URL: {current_url}")

            # URL 离开了 publish/publish 通常说明发布成功
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
    """轻量发布：仅根据文件名构建内容，无需 advices 对象。

    适用于 --send-xhs 模式，直接发布已有图片。
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
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = f"{dt.month}/{dt.day}"
    except ValueError:
        date_display = date_str

    city_str = "·".join(city_names)
    special = get_special_day(date_str)

    # 标题
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
    lines.append(f"今日穿搭指南 {date_str}")
    for c in city_names:
        lines.append(f"📍 {c}")
    content = "\n".join(lines)

    # 标签
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
