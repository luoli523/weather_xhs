#!/usr/bin/env python3
"""Instagram 登录辅助脚本

使用 instagrapi 登录 Instagram 并保存 session 文件，
供后续自动化发布使用。支持 Challenge（安全验证）和 2FA（两步验证）。

用法：
    python scripts/ig_login.py

保存路径默认为 ~/.instagram/session.json，
也可通过环境变量 IG_SESSION_PATH 指定。

也可以从 .env 读取 IG_USERNAME / IG_PASSWORD，免去手动输入。
"""

import os
import sys
from pathlib import Path

# 项目根目录加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv()


DEFAULT_SESSION_PATH = os.path.expanduser("~/.instagram/session.json")


def _challenge_code_handler(username, choice):
    """Instagram Challenge 验证码回调。

    当 Instagram 检测到异常登录并发送验证码时，
    此函数会被 instagrapi 自动调用，等待用户输入验证码。
    """
    if choice == 0:
        hint = "短信"
    elif choice == 1:
        hint = "邮箱"
    else:
        hint = f"方式 {choice}"
    print()
    print(f"  📨 Instagram 已通过{hint}发送验证码")
    code = input(f"  📱 请输入收到的验证码: ").strip()
    return code


def _change_password_handler(username):
    """Instagram 要求修改密码时的回调（通常直接跳过）。"""
    print()
    print("  ⚠ Instagram 建议修改密码，此处跳过。")
    # 返回旧密码跳过修改
    return None


def login_and_save():
    """交互式登录 Instagram 并保存 session"""
    try:
        import instagrapi  # noqa: F401
    except ImportError:
        print("❌ 未安装 instagrapi，请先运行：")
        print("   pip install instagrapi")
        sys.exit(1)

    session_path = os.getenv("IG_SESSION_PATH", DEFAULT_SESSION_PATH).strip()

    # 确保目录存在
    Path(session_path).parent.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  Instagram 登录辅助工具")
    print("=" * 50)
    print()
    print(f"Session 保存路径: {session_path}")
    print()

    # 优先从 .env 读取，否则交互式输入
    username = os.getenv("IG_USERNAME", "").strip()
    password = os.getenv("IG_PASSWORD", "").strip()

    if username and password:
        print(f"📧 从 .env 读取用户名: {username}")
    else:
        username = input("📧 Instagram 用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            sys.exit(1)

        import getpass
        password = getpass.getpass("🔒 Instagram 密码: ").strip()
        if not password:
            print("❌ 密码不能为空")
            sys.exit(1)

    print()
    print("🔑 正在登录 Instagram...")

    from src.common.instagram import _new_client
    cl = _new_client()
    # 注册 challenge 回调，让用户在终端输入验证码
    cl.challenge_code_handler = _challenge_code_handler
    cl.change_password_handler = _change_password_handler

    try:
        cl.login(username, password)
    except Exception as e:
        error_msg = str(e).lower()

        if "two_factor" in error_msg or "2fa" in error_msg:
            print()
            print("⚠ 需要两步验证（2FA）。")
            code = input("📱 请输入验证码: ").strip()
            if code:
                try:
                    cl.login(username, password, verification_code=code)
                except Exception as e2:
                    print(f"❌ 2FA 登录失败: {e2}")
                    sys.exit(1)
            else:
                print("❌ 验证码不能为空")
                sys.exit(1)

        elif "challenge" in error_msg:
            print()
            print("⚠ Instagram 要求安全验证（Challenge Required）。")
            print("  验证码应该已经发送到你的邮箱或手机。")
            print("  如果没有收到验证码提示，请先在手机 App 中确认登录，")
            print("  然后重新运行本脚本。")
            sys.exit(1)

        else:
            print(f"❌ 登录失败: {e}")
            sys.exit(1)

    # 保存 session
    cl.dump_settings(session_path)

    print()
    print(f"✅ 登录成功！Session 已保存到: {session_path}")
    print()

    # 验证：获取账号信息
    try:
        info = cl.account_info()
        print(f"  用户名: {info.username}")
        print(f"  全名: {info.full_name}")
        print(f"  粉丝数: {info.follower_count}")
        print()
    except Exception:
        pass

    print("后续使用提示：")
    print("  - 在 .env 中确保以下配置：")
    print("      IG_ENABLED=true")
    print(f"      IG_USERNAME={username}")
    print("      IG_PASSWORD=<你的密码>")
    print("  - 运行 python main.py 即可自动发布到 Instagram")
    print()
    print("GitHub Actions 使用提示：")
    print("  在 GitHub 仓库 Settings → Secrets 中添加：")
    print("    IG_USERNAME - Instagram 用户名")
    print("    IG_PASSWORD - Instagram 密码")
    print("  Session 会在 CI 中自动通过账密创建。")


def main():
    login_and_save()


if __name__ == "__main__":
    main()
