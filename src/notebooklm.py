"""NotebookLM 自动化模块

使用 notebooklm-py 库实现：
1. 查找或创建 weather_xhs notebook
2. 上传 clothing_guide markdown 文件
3. 按城市逐张生成 infographic
4. 下载生成的图片
"""

import asyncio
import random
from pathlib import Path

import yaml
from notebooklm import NotebookLMClient, InfographicOrientation, InfographicDetail

from .clothing_index import ClothingAdvice

NOTEBOOK_TITLE = "weather_xhs"


def load_infographic_prompt(config_path: str = "config/prompts.yaml") -> str:
    """加载 infographic prompt 模板"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["infographic_prompt"]


def load_style_options(config_path: str = "config/style_options.yaml") -> dict:
    """加载风格变量选项配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def pick_style_values(style_options: dict, category: str) -> dict[str, str]:
    """根据穿衣等级，从选项列表中随机选取各风格变量的值。

    支持两种格式：
      - 纯列表：直接随机选一项（与天气无关）
      - 按穿衣等级分组的字典：先匹配 category，再随机选一项
    """
    values = {}
    for key, options in style_options.items():
        if isinstance(options, list):
            # 纯列表：直接随机
            values[key] = random.choice(options)
        elif isinstance(options, dict):
            # 按穿衣等级分组：先匹配，再随机
            if category in options:
                values[key] = random.choice(options[category])
            else:
                # fallback: 从所有分组中随机选
                all_items = [item for group in options.values() for item in group]
                values[key] = random.choice(all_items) if all_items else ""
    return values


def build_city_prompt(template: str, advice: ClothingAdvice, style_options: dict) -> str:
    """用天气数据 + 随机风格变量填充 prompt 模板"""
    tips_text = "\n".join(f"- {t}" for t in advice.extra_tips) if advice.extra_tips else "无"

    # 随机选取风格变量
    style_values = pick_style_values(style_options, advice.clothing_category)

    # 合并天气数据和风格变量
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


async def find_or_create_notebook(client: NotebookLMClient) -> str:
    """查找 weather_xhs notebook，不存在则创建。返回 notebook_id"""
    notebooks = await client.notebooks.list()
    for nb in notebooks:
        if nb.title == NOTEBOOK_TITLE:
            print(f"  找到已有 notebook: {NOTEBOOK_TITLE} (id={nb.id[:8]}...)")
            return nb.id

    print(f"  未找到 {NOTEBOOK_TITLE}，正在创建...")
    nb = await client.notebooks.create(NOTEBOOK_TITLE)
    print(f"  已创建 notebook: {NOTEBOOK_TITLE} (id={nb.id[:8]}...)")
    return nb.id


async def upload_source(client: NotebookLMClient, notebook_id: str, md_file: str) -> str:
    """上传 markdown 文件到 notebook，返回 source_id。

    如果 notebook 中已有同名 source，先删除再上传。
    """
    file_path = Path(md_file)
    file_name = file_path.name

    # 检查是否有同名 source，有则删除
    existing_sources = await client.sources.list(notebook_id)
    for src in existing_sources:
        if src.title == file_name:
            print(f"  发现同名 source: {file_name}，正在删除旧版本...")
            await client.sources.delete(notebook_id, src.id)

    print(f"  正在上传: {file_name}")
    source = await client.sources.add_file(notebook_id, str(file_path), wait=True)
    print(f"  上传完成: source_id={source.id[:8]}... title={source.title}")
    return source.id


async def generate_city_infographics(
    client: NotebookLMClient,
    notebook_id: str,
    source_id: str,
    advices: list[ClothingAdvice],
    output_dir: str,
) -> list[str]:
    """按城市逐张生成 infographic 并下载。返回生成的文件路径列表。"""
    prompt_template = load_infographic_prompt()
    style_options = load_style_options()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded_files = []

    for i, advice in enumerate(advices):
        city_prompt = build_city_prompt(prompt_template, advice, style_options)
        print(f"\n  [{i+1}/{len(advices)}] 正在生成 {advice.city_name} 穿搭图...")

        # 生成 infographic，仅使用指定的 source
        status = await client.artifacts.generate_infographic(
            notebook_id,
            source_ids=[source_id],
            instructions=city_prompt,
            orientation=InfographicOrientation.PORTRAIT,
            detail_level=InfographicDetail.DETAILED,
            language="zh",
        )

        # 等待生成完成
        print(f"    等待生成完成 (task_id={status.task_id[:8]}...)...")
        await client.artifacts.wait_for_completion(
            notebook_id, status.task_id, timeout=300
        )

        # 在 notebook 中重命名，方便区分
        artifact_name = f"{advice.city_name}_{advice.date}"
        await client.artifacts.rename(notebook_id, status.task_id, artifact_name)
        print(f"    已命名: {artifact_name}")

        # 下载图片，保持与 notebook 中一致的命名
        out_file = str(output_path / f"{artifact_name}.png")
        await client.artifacts.download_infographic(
            notebook_id, out_file, artifact_id=status.task_id
        )
        downloaded_files.append(out_file)
        print(f"    已下载: {out_file}")

    return downloaded_files


async def run_notebooklm_pipeline(
    md_file: str,
    advices: list[ClothingAdvice],
    output_dir: str,
) -> list[str]:
    """完整的 NotebookLM pipeline：上传 → 生成 → 下载"""
    print("\n📓 NotebookLM Pipeline 开始")

    async with await NotebookLMClient.from_storage() as client:
        # 1. 查找或创建 notebook
        print("\n[1/3] 查找 notebook...")
        notebook_id = await find_or_create_notebook(client)

        # 2. 上传 source
        print("\n[2/3] 上传 source...")
        source_id = await upload_source(client, notebook_id, md_file)

        # 3. 按城市生成 infographic
        print(f"\n[3/3] 生成 {len(advices)} 张穿搭 infographic...")
        files = await generate_city_infographics(
            client, notebook_id, source_id, advices, output_dir
        )

        print(f"\n📓 NotebookLM Pipeline 完成，共生成 {len(files)} 张图片")
        return files
