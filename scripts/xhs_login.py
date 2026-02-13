#!/usr/bin/env python3
"""小红书登录辅助脚本

启动有头浏览器让用户手动登录小红书创作者平台，
登录成功后将 cookies 和 localStorage 保存为 storage_state.json，
供后续自动化发布使用。

用法：
    python scripts/xhs_login.py

保存路径默认为 ~/.xhs/storage_state.json，
也可通过环境变量 XHS_STORAGE_STATE_PATH 指定。
"""

import asyncio
import os
import sys
from pathlib import Path

# 项目根目录加入 sys.path（以便复用项目常量）
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


DEFAULT_STORAGE_STATE_PATH = os.path.expanduser("~/.xhs/storage_state.json")
CREATOR_URL = "https://creator.xiaohongshu.com"


async def login_and_save():
    """启动浏览器，等待用户登录，保存 storage_state"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ 未安装 playwright，请先运行：")
        print("   pip install playwright && playwright install chromium")
        sys.exit(1)

    storage_state_path = os.getenv(
        "XHS_STORAGE_STATE_PATH", DEFAULT_STORAGE_STATE_PATH
    ).strip()

    # 确保目录存在
    state_dir = Path(storage_state_path).parent
    state_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  小红书登录辅助工具")
    print("=" * 50)
    print()
    print(f"即将打开浏览器，请在浏览器中登录小红书创作者平台。")
    print(f"登录成功后，回到此终端按回车键保存登录状态。")
    print(f"保存路径: {storage_state_path}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        print("🌐 正在打开小红书创作者平台...")
        await page.goto(CREATOR_URL, wait_until="networkidle")

        print()
        print("👉 请在浏览器中完成登录（扫码或手机号登录均可）")
        print()

        # 等待用户在终端按回车
        input("✅ 登录完成后，按回车键保存登录状态...")

        # 保存 storage_state
        await context.storage_state(path=storage_state_path)
        print()
        print(f"✅ 登录状态已保存到: {storage_state_path}")
        print()
        print("后续使用提示：")
        print("  - 自动发布：设置 XHS_ENABLED=true 后运行 python main.py")
        print("  - 如果 cookie 过期，重新运行本脚本即可")
        print()

        # CI/CD 使用提示
        print("GitHub Actions 使用提示：")
        print("  将 storage_state.json 编码为 base64 存入 Secret：")
        print(f"  base64 < {storage_state_path}")
        print("  然后在 GitHub 仓库 Settings → Secrets 中添加 XHS_STORAGE_STATE")

        await browser.close()


def main():
    asyncio.run(login_and_save())


if __name__ == "__main__":
    main()
