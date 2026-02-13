"""天气穿搭指南生成系统

主流程：读取配置 → 获取天气 → 生成穿衣指数 → 输出 Markdown
     → 上传 NotebookLM → 用 NotebookLM 内置 infographic 工具按城市生成穿搭图片
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.weather import OpenWeatherClient
from src.mock_weather import MockWeatherClient
from src.clothing_index import generate_clothing_advice
from src.content_generator import generate_markdown, save_markdown


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
    return parser.parse_args()


def load_config(config_path: str = "config/config.yaml", require_api_key: bool = True) -> dict:
    """加载配置文件，支持环境变量替换"""
    load_dotenv()
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 替换环境变量引用
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


async def main():
    args = parse_args()
    use_mock = args.mock
    skip_notebooklm = args.no_nlm

    # 映射 CLI gender 参数到中文 key（与 style_options.yaml 一致）
    _gender_map = {"female": "女性", "male": "男性", "neutral": "中性"}
    gender = _gender_map.get(args.gender) if args.gender != "random" else None

    print("=== 天气穿搭指南生成系统 ===\n")
    if use_mock:
        print("⚠ Mock 模式：使用模拟天气数据\n")
    if gender:
        print(f"👤 人物性别：{gender}\n")

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
    today = datetime.now().strftime("%Y-%m-%d")
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
            from src.notebooklm import run_notebooklm_pipeline
        except ImportError as e:
            print(f"\n❌ NotebookLM 依赖未安装: {e}")
            print("请先安装依赖：pip install -r requirements.txt")
            sys.exit(1)

        image_files = await run_notebooklm_pipeline(
            md_file=str(output_file),
            advices=advices,
            output_dir=str(output_dir),
            gender=gender,
        )
        print(f"\n🎨 生成的穿搭图片:")
        for f in image_files:
            print(f"  {f}")

    print("\n✅ 全部完成！")


if __name__ == "__main__":
    asyncio.run(main())
