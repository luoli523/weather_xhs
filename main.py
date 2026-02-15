"""天气穿搭指南生成系统

主流程：读取配置 → 获取天气 → 生成穿衣指数 → 输出 Markdown
     → 上传 NotebookLM → 用 NotebookLM 内置 infographic 工具按城市生成穿搭图片
     → 推送 Telegram → 发布小红书 → 发布 Instagram
     → 节气检测 → 节气 infographic → 推送 Telegram → 发布小红书 → 发布 Instagram
     → 诗词检测（GPT）→ 诗词 infographic → 推送 Telegram → 发布小红书 → 发布 Instagram
"""

import asyncio
import argparse
import os
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
from src.clothing.xhs import publish_images as xhs_publish_images
from src.clothing.instagram import publish_images as ig_publish_images

# ── 共享模块 ──
from src.common.telegram import send_photo as telegram_send_photo, send_message as telegram_send_message, get_telegram_config
from src.common.xhs import get_xhs_config, publish_note
from src.common.instagram import get_ig_config, publish_album as ig_publish_album

# ── 节气模块 ──
from src.solar_term.detector import get_solar_term
from src.solar_term.content import (
    generate_markdown as solar_term_generate_markdown,
    save_markdown as solar_term_save_markdown,
    build_xhs_content as solar_term_build_xhs_content,
    build_telegram_caption as solar_term_build_telegram_caption,
    build_ig_caption as solar_term_build_ig_caption,
)

# ── 诗词模块 ──
from src.poetry.detector import get_poem
from src.poetry.content import (
    generate_markdown as poetry_generate_markdown,
    save_markdown as poetry_save_markdown,
    build_xhs_content as poetry_build_xhs_content,
    build_telegram_caption as poetry_build_telegram_caption,
    build_ig_caption as poetry_build_ig_caption,
)


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
    parser.add_argument("--no-xhs", action="store_true", help="跳过小红书发布")
    parser.add_argument("--no-ig", action="store_true", help="跳过 Instagram 发布")
    parser.add_argument("--no-poetry", action="store_true", help="跳过诗词模块（不调用 GPT）")
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


# ── 节气专属流程 ──


async def _run_solar_term_pipeline(
    solar_term: dict,
    today: str,
    output_dir: Path,
    skip_notebooklm: bool,
    args: argparse.Namespace,
):
    """节气专属流程：生成 Markdown → NotebookLM infographic → Telegram → 小红书"""

    # 8a. 生成节气 Markdown
    md_content = solar_term_generate_markdown(solar_term)
    md_file = output_dir / f"solar_term_{solar_term['name']}_{today}.md"
    solar_term_save_markdown(md_content, str(md_file))
    print(f"  📄 节气 Markdown: {md_file}")

    if skip_notebooklm:
        print("  ⏭ 跳过 NotebookLM（--no-nlm）")
        return

    # 8b. NotebookLM 生成节气 infographic
    try:
        from src.solar_term.notebooklm import run_pipeline as solar_term_run_pipeline
    except ImportError as e:
        print(f"  ❌ NotebookLM 依赖未安装: {e}")
        return

    # 使用 GPT 动态生成的 infographic prompt
    prompt = solar_term.get("infographic_prompt", "")
    if not prompt:
        print("  ⚠ GPT 未返回节气 infographic prompt，跳过 infographic 生成")
        return

    artifact_name = f"{solar_term['name']}_{today}"

    solar_image = await solar_term_run_pipeline(
        md_file=str(md_file),
        prompt=prompt,
        artifact_name=artifact_name,
        output_dir=str(output_dir),
    )

    if not solar_image:
        print("  ❌ 节气 infographic 生成失败")
        return

    print(f"  🎨 节气图片: {solar_image}")

    # 8c. Telegram 发送节气图片
    tg_config = get_telegram_config()
    if tg_config:
        bot_token, chat_id = tg_config
        caption = solar_term_build_telegram_caption(solar_term)
        print(f"  📱 推送节气图片到 Telegram...")
        ok = await telegram_send_photo(bot_token, chat_id, solar_image, caption=caption)
        if ok:
            print(f"  ✅ 节气图片已推送到 Telegram")
        else:
            print(f"  ⚠ 节气图片 Telegram 推送失败")
    else:
        print("  ⏭ Telegram 未配置，跳过节气推送")

    # 8d. 小红书发布节气笔记
    if hasattr(args, "no_xhs") and args.no_xhs:
        print("  ⏭ 跳过小红书（--no-xhs）")
    else:
        xhs_config = get_xhs_config()
        if xhs_config:
            title, content, tags = solar_term_build_xhs_content(solar_term)
            print(f"  📕 发布节气笔记到小红书...")
            print(f"    标题: {title}")
            success = await publish_note(
                image_files=[solar_image],
                title=title,
                content=content,
                tags=tags,
                storage_state_path=xhs_config["storage_state_path"],
            )
            if success:
                print(f"  ✅ 节气笔记已发布到小红书")
            else:
                print(f"  ⚠ 节气笔记小红书发布失败")
        else:
            print("  ⏭ 小红书未配置，跳过节气发布")

    # 8e. Instagram 发布节气帖子
    if hasattr(args, "no_ig") and args.no_ig:
        print("  ⏭ 跳过 Instagram（--no-ig）")
    else:
        ig_config = get_ig_config()
        if ig_config:
            caption = solar_term_build_ig_caption(solar_term)
            print(f"  📷 发布节气帖子到 Instagram...")
            success = await ig_publish_album(
                image_files=[solar_image],
                caption=caption,
                config=ig_config,
            )
            if success:
                print(f"  ✅ 节气帖子已发布到 Instagram")
            else:
                print(f"  ⚠ 节气帖子 Instagram 发布失败")
        else:
            print("  ⏭ Instagram 未配置，跳过节气发布")


# ── 诗词专属流程 ──


async def _run_poetry_pipeline(
    poem: dict,
    today: str,
    output_dir: Path,
    skip_notebooklm: bool,
    args: argparse.Namespace,
):
    """诗词专属流程：生成 Markdown → NotebookLM infographic → Telegram → 小红书 → Instagram"""

    occasion = poem.get("occasion", "诗词")

    # 9a. 生成诗词 Markdown
    md_content = poetry_generate_markdown(poem)
    md_file = output_dir / f"poetry_{occasion}_{today}.md"
    poetry_save_markdown(md_content, str(md_file))
    print(f"  📄 诗词 Markdown: {md_file}")

    if skip_notebooklm:
        print("  ⏭ 跳过 NotebookLM（--no-nlm）")
        return

    # 9b. NotebookLM 生成诗词 infographic
    try:
        from src.poetry.notebooklm import run_pipeline as poetry_run_pipeline
    except ImportError as e:
        print(f"  ❌ NotebookLM 依赖未安装: {e}")
        return

    # 使用 GPT 动态生成的 infographic prompt
    prompt = poem.get("infographic_prompt", "")
    if not prompt:
        print("  ⚠ GPT 未返回 infographic prompt，跳过")
        return

    artifact_name = f"诗词_{occasion}_{today}"

    poetry_image = await poetry_run_pipeline(
        md_file=str(md_file),
        prompt=prompt,
        artifact_name=artifact_name,
        output_dir=str(output_dir),
    )

    if not poetry_image:
        print("  ❌ 诗词 infographic 生成失败")
        return

    print(f"  🎨 诗词图片: {poetry_image}")

    # 9c. Telegram 发送诗词图片
    tg_config = get_telegram_config()
    if tg_config:
        bot_token, chat_id = tg_config
        caption = poetry_build_telegram_caption(poem)
        print(f"  📱 推送诗词图片到 Telegram...")
        ok = await telegram_send_photo(bot_token, chat_id, poetry_image, caption=caption)
        if ok:
            print(f"  ✅ 诗词图片已推送到 Telegram")
        else:
            print(f"  ⚠ 诗词图片 Telegram 推送失败")
    else:
        print("  ⏭ Telegram 未配置，跳过诗词推送")

    # 9d. 小红书发布诗词笔记
    if hasattr(args, "no_xhs") and args.no_xhs:
        print("  ⏭ 跳过小红书（--no-xhs）")
    else:
        xhs_config = get_xhs_config()
        if xhs_config:
            title, content, tags = poetry_build_xhs_content(poem)
            print(f"  📕 发布诗词笔记到小红书...")
            print(f"    标题: {title}")
            success = await publish_note(
                image_files=[poetry_image],
                title=title,
                content=content,
                tags=tags,
                storage_state_path=xhs_config["storage_state_path"],
            )
            if success:
                print(f"  ✅ 诗词笔记已发布到小红书")
            else:
                print(f"  ⚠ 诗词笔记小红书发布失败")
        else:
            print("  ⏭ 小红书未配置，跳过诗词发布")

    # 9e. Instagram 发布诗词帖子
    if hasattr(args, "no_ig") and args.no_ig:
        print("  ⏭ 跳过 Instagram（--no-ig）")
    else:
        ig_config = get_ig_config()
        if ig_config:
            caption = poetry_build_ig_caption(poem)
            print(f"  📷 发布诗词帖子到 Instagram...")
            success = await ig_publish_album(
                image_files=[poetry_image],
                caption=caption,
                config=ig_config,
            )
            if success:
                print(f"  ✅ 诗词帖子已发布到 Instagram")
            else:
                print(f"  ⚠ 诗词帖子 Instagram 发布失败")
        else:
            print("  ⏭ Instagram 未配置，跳过诗词发布")


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

    # 5. NotebookLM: 上传 → 生成 infographic → 下载
    if skip_notebooklm:
        print("\n⏭ 跳过 NotebookLM（--no-nlm）")
    else:
        try:
            from src.clothing.notebooklm import run_pipeline as clothing_run_pipeline
        except ImportError as e:
            print(f"\n❌ NotebookLM 依赖未安装: {e}")
            print("请先安装依赖：pip install -r requirements.txt")
            sys.exit(1)

        image_files = await clothing_run_pipeline(
            md_file=str(output_file),
            advices=advices,
            output_dir=str(output_dir),
            gender=gender,
        )
        print(f"\n🎨 生成的穿搭图片:")
        for f in image_files:
            print(f"  {f}")

        # 6. 推送到 Telegram
        await telegram_send_images(image_files, advices, date=today)

        # 7. 发布到小红书
        if args.no_xhs:
            print("\n⏭ 跳过小红书（--no-xhs）")
        else:
            await xhs_publish_images(image_files, advices, date=today)

        # 7b. 发布到 Instagram
        if args.no_ig:
            print("\n⏭ 跳过 Instagram（--no-ig）")
        else:
            await ig_publish_images(image_files, advices, date=today)

    # ── 8. 节气检测与专属内容生成 ──
    solar_term = await get_solar_term(today)
    if solar_term:
        print(f"\n🌿 今日节气：{solar_term['name']}！启动节气内容生成流程...")
        await _run_solar_term_pipeline(solar_term, today, output_dir, skip_notebooklm, args)
    else:
        print(f"\n🌿 今日非节气日，跳过节气内容生成")

    # ── 9. 诗词检测（GPT 动态匹配）与专属内容生成 ──
    if args.no_poetry:
        print(f"\n📜 跳过诗词模块（--no-poetry）")
    else:
        print(f"\n📜 正在调用 GPT 检测今日诗词...")
        poem = await get_poem(today)
        if poem:
            print(f"📜 今日诗词：《{poem['title']}》（{poem['dynasty']}·{poem['author']}）— {poem.get('occasion', '')}")
            await _run_poetry_pipeline(poem, today, output_dir, skip_notebooklm, args)
        else:
            print(f"📜 今日无匹配诗词，跳过")

    print("\n✅ 全部完成！")


if __name__ == "__main__":
    asyncio.run(main())
