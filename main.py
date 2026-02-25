"""天气穿搭指南生成系统

主流程：读取配置 → 获取天气 → 生成穿衣指数 → 输出 Markdown
     → 上传 NotebookLM → 用 NotebookLM 内置 infographic 工具按城市生成穿搭图片
     → 推送 Telegram → 发布 Instagram
"""

import asyncio
import argparse
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── 穿搭模块 ──
from src.clothing.weather import OpenWeatherClient
from src.clothing.mock_weather import MockWeatherClient
from src.clothing.index import generate_clothing_advice
from src.clothing.content import generate_markdown, save_markdown
from src.clothing.telegram import send_images as telegram_send_images
from src.clothing.telegram import send_images_simple as telegram_send_simple
from src.clothing.instagram import publish_images as ig_publish_images

# ── 共享模块 ──
from src.common.telegram import send_message as telegram_send_message, get_telegram_config
from src.common.notebooklm import check_auth as check_nlm_auth


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="天气穿搭指南生成系统")
    parser.add_argument("--mock", action="store_true", help="使用模拟天气数据")
    parser.add_argument("--no-nlm", action="store_true", help="跳过 NotebookLM 生成流程")
    parser.add_argument(
        "--gender",
        choices=["female", "male", "neutral", "random"],
        default="female",
        help="指定人物性别 (female=女性, male=男性, neutral=中性, random=随机)，默认 female",
    )
    parser.add_argument("--no-ig", action="store_true", help="跳过 Instagram 发布")
    parser.add_argument(
        "--send-telegram",
        action="store_true",
        help="跳过生成流程，仅发送当天已有图片到 Telegram",
    )
    parser.add_argument(
        "--send-xhs",
        action="store_true",
        help="跳过生成流程，仅发送当天已有图片到小红书",
    )
    parser.add_argument(
        "--send-ig",
        action="store_true",
        help="跳过生成流程，仅发送当天已有图片到 Instagram",
    )
    return parser.parse_args()


def load_config(config_path: str = "config/config.yaml", require_api_key: bool = True) -> dict:
    """加载配置文件，支持环境变量替换"""
    load_dotenv()
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    api_key = config["openweathermap"]["api_key"]
    if api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.getenv(env_var)
        if require_api_key and not api_key:
            print(f"错误：环境变量 {env_var} 未设置。请在 .env 文件中配置。")
            sys.exit(1)
        config["openweathermap"]["api_key"] = api_key or ""

    return config


async def fetch_all_weather(config: dict, use_mock: bool = False) -> list:
    """并发获取所有城市天气"""
    if use_mock:
        client = MockWeatherClient()
    else:
        client = OpenWeatherClient(
            api_key=config["openweathermap"]["api_key"],
        )

    tasks = [
        client.get_city_weather(city["name"], city["location_id"])
        for city in config["cities"]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    city_weathers = []
    for city_cfg, result in zip(config["cities"], results):
        if isinstance(result, Exception):
            print(f"⚠ 获取 {city_cfg['name']} 天气失败: {result}")
        else:
            city_weathers.append(result)

    return city_weathers


# ── 主流程 ──


async def main():
    args = parse_args()
    use_mock = args.mock
    skip_notebooklm = args.no_nlm

    _gender_map = {"female": "女性", "male": "男性", "neutral": "中性"}
    gender = _gender_map.get(args.gender) if args.gender != "random" else None

    print("=== 天气穿搭指南生成系统 ===\n")

    # --send-telegram / --send-xhs / --send-ig 模式：跳过生成，直接发送当天已有图片
    if args.send_telegram or args.send_xhs or args.send_ig:
        load_dotenv()
        today = datetime.now().strftime("%Y-%m-%d")
        output_dir = Path("output")
        images = sorted(output_dir.glob(f"*_{today}.png"))
        if not images:
            print(f"❌ 未找到当天图片（{output_dir}/*_{today}.png）")
            sys.exit(1)
        print(f"📱 发送模式：找到 {len(images)} 张当天图片")
        for img in images:
            print(f"  {img}")
        image_paths = [str(p) for p in images]
        if args.send_telegram:
            await telegram_send_simple(image_paths, date=today)
        if args.send_xhs:
            from src.clothing.xhs import publish_images_simple as xhs_publish_simple
            await xhs_publish_simple(image_paths, date_str=today)
        if args.send_ig:
            from src.clothing.instagram import publish_images_simple as ig_publish_simple
            await ig_publish_simple(image_paths, date_str=today)
        print("\n✅ 完成！")
        return

    if use_mock:
        print("⚠ Mock 模式：使用模拟天气数据\n")
    if gender:
        print(f"👤 人物性别：{gender}\n")

    # 0. 检查 OPENAI_API_KEY（GPT 动态生成 prompt 的必要条件）
    load_dotenv()
    today = datetime.now().strftime("%Y-%m-%d")

    if not os.getenv("OPENAI_API_KEY", "").strip():
        print("⚠ OPENAI_API_KEY 未配置，跳过当日全部生成流程")
        tg_config = get_telegram_config()
        if tg_config:
            bot_token, chat_id = tg_config
            await telegram_send_message(
                bot_token, chat_id,
                f"⚠️ <b>当日未执行通知</b>\n\n"
                f"📅 日期：{today}\n"
                f"❌ 原因：OPENAI_API_KEY 未配置\n"
                f"💡 请在 .env 或 GitHub Secrets 中配置后重试",
            )
            print("📱 已通过 Telegram 发送未执行通知")
        else:
            print("⚠ Telegram 也未配置，无法发送通知")
        return

    # 1. 加载配置
    config = load_config(require_api_key=not use_mock)
    cities = config["cities"]
    print(f"📋 已配置 {len(cities)} 个城市: {', '.join(c['name'] for c in cities)}")

    # 2. 获取天气数据
    print("\n🌤 正在获取天气数据...")
    city_weathers = await fetch_all_weather(config, use_mock=use_mock)
    if not city_weathers:
        print("❌ 未能获取任何城市的天气数据，退出。")
        sys.exit(1)
    print(f"✅ 成功获取 {len(city_weathers)} 个城市的天气数据")

    # 3. 生成穿衣指数
    print("\n👔 正在生成穿搭建议...")
    advices = [generate_clothing_advice(w) for w in city_weathers]
    for adv in advices:
        print(f"  {adv.city_name}: {adv.temp_range} | {adv.clothing_category}")

    # 4. 生成 Markdown 内容
    markdown_content = generate_markdown(advices, date=today)

    output_dir = Path(config["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"clothing_guide_{today}.md"
    save_markdown(markdown_content, str(output_file))
    print(f"\n📄 Markdown 文件已生成: {output_file}")

    # 5. 随机选取城市生成信息图
    infographic_count = config.get("infographic_count", 2)
    if len(advices) > infographic_count:
        selected_advices = random.sample(advices, infographic_count)
        print(f"\n🎲 从 {len(advices)} 个城市中随机选取 {infographic_count} 个生成信息图: "
              f"{', '.join(a.city_name for a in selected_advices)}")
    else:
        selected_advices = advices

    # 6. NotebookLM: 上传 → 生成 infographic → 下载
    if skip_notebooklm:
        print("\n⏭ 跳过 NotebookLM（--no-nlm）")
    else:
        # 6a. 先检测 NotebookLM 认证是否有效
        print("\n🔑 检测 NotebookLM 认证...")
        nlm_auth_ok = await check_nlm_auth()
        if not nlm_auth_ok:
            print("❌ NotebookLM 认证失效，跳过所有 infographic 生成")
            skip_notebooklm = True
            tg_config = get_telegram_config()
            if tg_config:
                bot_token, chat_id = tg_config
                await telegram_send_message(
                    bot_token, chat_id,
                    f"⚠️ <b>NotebookLM 认证失效</b>\n\n"
                    f"📅 日期：{today}\n"
                    f"❌ 无法生成 infographic，已跳过\n"
                    f"💡 请执行 <code>notebooklm login</code> 重新登录，\n"
                    f"然后更新 GitHub Secret：\n"
                    f"<code>base64 &lt; ~/.notebooklm/storage_state.json | gh secret set NOTEBOOKLM_STORAGE_STATE</code>",
                )
                print("📱 已通过 Telegram 发送认证失效通知")

        if not skip_notebooklm:
            try:
                from src.clothing.notebooklm import run_pipeline as clothing_run_pipeline
            except ImportError as e:
                print(f"\n❌ NotebookLM 依赖未安装: {e}")
                print("请先安装依赖：pip install -r requirements.txt")
                sys.exit(1)

            image_files = await clothing_run_pipeline(
                md_file=str(output_file),
                advices=selected_advices,
                output_dir=str(output_dir),
                gender=gender,
            )
            print(f"\n🎨 生成的穿搭图片:")
            for f in image_files:
                print(f"  {f}")

            # 7. 推送到 Telegram
            await telegram_send_images(image_files, selected_advices, date=today)

            # 8. 发布到 Instagram
            if args.no_ig:
                print("\n⏭ 跳过 Instagram（--no-ig）")
            else:
                await ig_publish_images(image_files, selected_advices, date=today)

    print("\n✅ 全部完成！")


if __name__ == "__main__":
    asyncio.run(main())
