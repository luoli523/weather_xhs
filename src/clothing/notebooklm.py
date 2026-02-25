"""穿搭 NotebookLM Pipeline

按城市生成穿搭 infographic：调用 GPT 动态生成 prompt → 逐城市生成 → 下载图片。
如果 LLM API Key 未配置，回退到内置的基础 prompt。
"""

import asyncio
import os
from pathlib import Path

from notebooklm import NotebookLMClient

from src.common.notebooklm import find_or_create_notebook, upload_source, create_infographic_with_retry

INFOGRAPHIC_INTERVAL = 30  # 每张 infographic 之间的间隔（秒），避免触发 NotebookLM 限流
from .index import ClothingAdvice


# ── GPT 动态 Prompt 生成 ──

CLOTHING_SYSTEM_PROMPT = """\
你是一位时装插画信息图设计师。给定一个城市的天气数据和穿搭建议，
请生成一段完整的信息图生成指令（prompt），用于生成一张时装解析风格的信息图插画。

视觉风格要求（固定，必须包含在输出中）：
– 半写实动漫风时装插画
– 柔和阴影，清晰线稿，优雅比例
– 极简黑色箭头标注与短标签说明
– 局部材质细节强化（织纹、光泽、罗纹、纤维微距）
– 背景融入该城市的标志性城市元素（地标建筑、街景轮廓、城市天际线等），以淡化、简笔或半透明方式呈现，不抢主体
– 画面整体氛围反映当天天气状况，通过光影、色调、空气感营造真实天气氛围
– 信息图元素：3-6 个精简标注箭头指向剪裁或材质细节，可选局部材质色块或细节放大插图
– 竖版排版（PORTRAIT），印刷级清晰度，整体精致
– 整体气质：当代时装技术解析插画风格，介于时装速写与产品结构图之间

你需要根据天气和穿搭建议动态决定以下内容，使每次生成都有变化和新鲜感：
1. 主体人物的外观描述（具体的年龄、发型、妆容、身材、气质，要有画面感）
2. 性别气质呈现（根据指定的性别倾向）
3. 3-5 个核心穿搭单品的具体描述（含面料、材质、剪裁细节）
4. 鞋履和配饰搭配
5. 整体配色方案（契合天气、季节和穿衣等级，给出具体色彩名称）
6. 情绪氛围（如松弛感日常、精致通勤、文艺慵懒、都市简约等）

直接输出完整的 prompt 文本（400-600字），不要输出 JSON 或其他格式包裹。
不要输出任何前导说明或结尾总结，只输出 prompt 本身。"""

CLOTHING_USER_TEMPLATE = """\
城市：{city}
日期：{date}
天气：{weather}
温度：{temp_range}（体感 {feels_like}）
穿衣等级：{category}
穿搭建议：{outfit}
小贴士：{tips}
人物性别倾向：{gender}

请生成这张穿搭信息图的完整 prompt。"""


async def generate_city_prompt_via_gpt(
    advice: ClothingAdvice,
    gender: str | None = None,
) -> str | None:
    """调用 GPT 为指定城市动态生成穿搭 infographic prompt。

    Returns:
        完整的 prompt 文本，失败返回 None
    """
    from src.common.config import get_llm_config
    llm = get_llm_config()
    if not llm["api_key"]:
        return None

    tips_text = "\n".join(f"- {t}" for t in advice.extra_tips) if advice.extra_tips else "无"
    gender_text = gender or "不限，自由发挥"

    user_prompt = CLOTHING_USER_TEMPLATE.format(
        city=advice.city_name,
        date=advice.date,
        weather=advice.weather_desc,
        temp_range=advice.temp_range,
        feels_like=advice.feels_like,
        category=advice.clothing_category,
        outfit=advice.outfit_suggestion,
        tips=tips_text,
        gender=gender_text,
    )

    try:
        from openai import AsyncOpenAI

        client_kwargs = {"api_key": llm["api_key"]}
        if llm["base_url"]:
            client_kwargs["base_url"] = llm["base_url"]
        client = AsyncOpenAI(**client_kwargs)
        response = await client.chat.completions.create(
            model=llm["model"],
            messages=[
                {"role": "system", "content": CLOTHING_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=llm["max_completion_tokens"],
        )

        content = response.choices[0].message.content
        if content and len(content.strip()) > 50:
            return content.strip()

        print(f"    ⚠ GPT 返回内容过短，回退到基础 prompt")
        return None

    except Exception as e:
        print(f"    ⚠ GPT prompt 生成失败: {type(e).__name__}: {e}")
        return None


def _build_fallback_prompt(advice: ClothingAdvice, gender: str | None = None) -> str:
    """当 GPT 不可用时的基础回退 prompt。"""
    tips_text = "\n".join(f"- {t}" for t in advice.extra_tips) if advice.extra_tips else "无"
    gender_desc = f"性别倾向：{gender}" if gender else ""

    return f"""请根据以下城市天气穿搭信息，生成一张时装解析信息图风格插画。

【天气与穿搭数据】
城市：{advice.city_name}
日期：{advice.date}
天气：{advice.weather_desc}
温度：{advice.temp_range}（体感 {advice.feels_like}）
穿衣等级：{advice.clothing_category}
穿搭建议：{advice.outfit_suggestion}
小贴士：
{tips_text}

【视觉风格指令】
一张时装解析信息图风格插画。
半写实动漫风时装插画，柔和阴影，清晰线稿，优雅比例。
背景融入{advice.city_name}的标志性城市元素，画面氛围反映当天天气。
{gender_desc}
3-5 个核心穿搭单品，含材质细节，自然围绕人物构图。
3-6 个精简标注箭头，指向剪裁或材质细节。
竖版排版，印刷级清晰度。"""


# ── NotebookLM Infographic 生成 ──

async def generate_city_infographics(
    client: NotebookLMClient,
    notebook_id: str,
    source_id: str,
    advices: list[ClothingAdvice],
    output_dir: str,
    gender: str | None = None,
) -> list[str]:
    """按城市逐张生成 infographic 并下载。返回生成的文件路径列表。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    downloaded_files = []

    for i, advice in enumerate(advices):
        print(f"\n  [{i+1}/{len(advices)}] 正在生成 {advice.city_name} 穿搭图...")

        # 尝试 GPT 动态生成 prompt，失败则回退
        city_prompt = await generate_city_prompt_via_gpt(advice, gender=gender)
        if city_prompt:
            print(f"    ✨ GPT 动态 prompt ({len(city_prompt)} 字)")
        else:
            city_prompt = _build_fallback_prompt(advice, gender=gender)
            print(f"    📋 回退到基础 prompt")

        status = await create_infographic_with_retry(
            client, notebook_id, source_id, city_prompt,
        )
        if not status:
            print(f"    ❌ {advice.city_name} infographic 创建失败，跳过")
            continue

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

        if i < len(advices) - 1:
            print(f"    ⏳ 等待 {INFOGRAPHIC_INTERVAL}s 后生成下一张...")
            await asyncio.sleep(INFOGRAPHIC_INTERVAL)

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
