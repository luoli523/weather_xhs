"""穿搭 NotebookLM Pipeline

按城市生成穿搭 infographic：加载 prompt 模板 + 风格变量 → 逐城市生成 → 下载图片。
"""

import random
from pathlib import Path

import yaml
from notebooklm import NotebookLMClient, InfographicOrientation, InfographicDetail

from src.common.notebooklm import find_or_create_notebook, upload_source
from .index import ClothingAdvice


def load_infographic_prompt(config_path: str = "config/prompts.yaml") -> str:
    """加载 infographic prompt 模板"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["infographic_prompt"]


def load_style_options(config_path: str = "config/style_options.yaml") -> dict:
    """加载风格变量选项配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def pick_style_values(
    style_options: dict, category: str, gender: str | None = None,
) -> dict[str, str]:
    """根据穿衣等级（和可选性别），从选项列表中随机选取各风格变量的值。"""
    values = {}
    for key, options in style_options.items():
        if isinstance(options, list):
            values[key] = random.choice(options)
        elif isinstance(options, dict):
            match_key = gender if key == "人物描述" else category
            if match_key and match_key in options:
                values[key] = random.choice(options[match_key])
            else:
                all_items = [item for group in options.values() for item in group]
                values[key] = random.choice(all_items) if all_items else ""
    return values


def build_city_prompt(
    template: str, advice: ClothingAdvice, style_options: dict,
    gender: str | None = None,
) -> str:
    """用天气数据 + 随机风格变量填充 prompt 模板"""
    tips_text = "\n".join(f"- {t}" for t in advice.extra_tips) if advice.extra_tips else "无"

    style_values = pick_style_values(style_options, advice.clothing_category, gender=gender)

    all_values = {
        "city": advice.city_name,
        "date": advice.date,
        "weather": advice.weather_desc,
        "temp_range": advice.temp_range,
        "feels_like": advice.feels_like,
        "category": advice.clothing_category,
        "outfit": advice.outfit_suggestion,
        "tips": tips_text,
        **style_values,
    }

    return template.format(**all_values)


async def generate_city_infographics(
    client: NotebookLMClient,
    notebook_id: str,
    source_id: str,
    advices: list[ClothingAdvice],
    output_dir: str,
    gender: str | None = None,
) -> list[str]:
    """按城市逐张生成 infographic 并下载。返回生成的文件路径列表。"""
    prompt_template = load_infographic_prompt()
    style_options = load_style_options()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded_files = []

    for i, advice in enumerate(advices):
        city_prompt = build_city_prompt(prompt_template, advice, style_options, gender=gender)
        print(f"\n  [{i+1}/{len(advices)}] 正在生成 {advice.city_name} 穿搭图...")

        status = await client.artifacts.generate_infographic(
            notebook_id,
            source_ids=[source_id],
            instructions=city_prompt,
            orientation=InfographicOrientation.PORTRAIT,
            detail_level=InfographicDetail.DETAILED,
            language="zh",
        )

        print(f"    等待生成完成 (task_id={status.task_id[:8]}...)...")
        await client.artifacts.wait_for_completion(
            notebook_id, status.task_id, timeout=300
        )

        artifact_name = f"{advice.city_name}_{advice.date}"
        await client.artifacts.rename(notebook_id, status.task_id, artifact_name)
        print(f"    已命名: {artifact_name}")

        out_file = str(output_path / f"{artifact_name}.png")
        await client.artifacts.download_infographic(
            notebook_id, out_file, artifact_id=status.task_id
        )
        downloaded_files.append(out_file)
        print(f"    已下载: {out_file}")

    return downloaded_files


async def run_pipeline(
    md_file: str,
    advices: list[ClothingAdvice],
    output_dir: str,
    gender: str | None = None,
) -> list[str]:
    """完整的穿搭 NotebookLM pipeline：上传 → 生成 → 下载"""
    print("\n📓 NotebookLM Pipeline 开始")

    async with await NotebookLMClient.from_storage() as client:
        print("\n[1/3] 查找 notebook...")
        notebook_id = await find_or_create_notebook(client)

        print("\n[2/3] 上传 source...")
        source_id = await upload_source(client, notebook_id, md_file)

        print(f"\n[3/3] 生成 {len(advices)} 张穿搭 infographic...")
        files = await generate_city_infographics(
            client, notebook_id, source_id, advices, output_dir, gender=gender
        )

        print(f"\n📓 NotebookLM Pipeline 完成，共生成 {len(files)} 张图片")
        return files
