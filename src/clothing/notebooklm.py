"""穿搭 NotebookLM Pipeline

按城市生成穿搭 infographic：调用 GPT 动态生成 prompt → 逐城市生成 → 下载图片。
如果 LLM API Key 未配置，回退到内置的基础 prompt。
"""

import asyncio
import os
import random
from pathlib import Path

from notebooklm import NotebookLMClient

from src.common.notebooklm import find_or_create_notebook, upload_source, create_infographic_with_retry

INFOGRAPHIC_INTERVAL = 30  # 每张 infographic 之间的间隔（秒），避免触发 NotebookLM 限流
from .index import ClothingAdvice


# ── 视觉风格库 ──

VISUAL_STYLES = [
    {
        "name": "日系少女漫画风",
        "desc": (
            "– 日系少女漫画（Shojo Manga）风格\n"
            "– 精致纤细线条，大而明亮的眼睛，柔焦光晕效果\n"
            "– 配色粉嫩清透，樱花粉/奶白/浅紫/薄荷绿为主\n"
            "– 背景干净简洁，带有花瓣、星星或气泡等少女感装饰元素\n"
            "– 服装蓬松感或 Y2K 感，蝴蝶结、蕾丝等细节丰富\n"
            "– 整体气质：可爱清新，日系杂志《SEVENTEEN》风"
        ),
    },
    {
        "name": "极简素描时装风",
        "desc": (
            "– 极简手绘铅笔/钢笔素描时装风格\n"
            "– 流畅单色线条，笔触带有速写感和节奏感\n"
            "– 人物比例夸张拉长（9-10 头身），姿态随性自然\n"
            "– 服装细节通过线条疏密变化表现材质，无填色或局部淡墨渲染\n"
            "– 背景极简或无背景，留白大量\n"
            "– 整体气质：时装周后台草图感，John Galliano 速写风"
        ),
    },
    {
        "name": "中国风水墨插画",
        "desc": (
            "– 中国风水墨时装插画风格\n"
            "– 水墨渲染为底，工笔细描勾勒服装细节，浓淡干湿变化丰富\n"
            "– 配色以墨色/朱砂/石青/赭石等中国传统色为主，点缀金色\n"
            "– 人物姿态含蓄优雅，融入传统纹样（云纹、回纹、缠枝花）\n"
            "– 背景以写意山水或建筑剪影烘托意境，大面积留白\n"
            "– 整体气质：东方美学与现代时装的融合，雅致大气"
        ),
    },
    {
        "name": "半写实动漫时装风",
        "desc": (
            "– 半写实动漫风时装插画（介于写实与动漫之间）\n"
            "– 柔和阴影过渡，清晰干净的线稿，人物比例优雅匀称\n"
            "– 面部五官精致但不夸张，皮肤与发丝带有真实光影质感\n"
            "– 服装材质通过光泽、织纹、褶皱细致刻画，接近产品结构图质感\n"
            "– 配色克制自然，层次丰富但不跳脱\n"
            "– 整体气质：当代时装技术解析插画，介于时装速写与产品结构图之间"
        ),
    },
    {
        "name": "可爱卡通动漫风",
        "desc": (
            "– Q 版可爱卡通动漫风格（Chibi / Kawaii）\n"
            "– 人物头身比约 2-3 头身，大头圆眼，表情生动夸张\n"
            "– 线条圆润流畅，无硬角，填色明亮饱和，类似 LINE Friends / 迪士尼 Tsum Tsum 质感\n"
            "– 服装简化为标志性色块和轮廓，配饰放大夸张，突出萌点\n"
            "– 背景活泼，带有气泡、爱心、星星、彩虹等可爱装饰元素\n"
            "– 整体气质：治愈萌系，充满活力和少女心"
        ),
    },
    {
        "name": "吉卜力手绘动画风",
        "desc": (
            "– 宫崎骏/吉卜力工作室手绘动画风格\n"
            "– 温润自然的水彩+铅笔底稿质感，线条柔和有手绘颤动感\n"
            "– 配色以大地色系为主（苔绿/土黄/天蓝/米白/暖橙），自然通透\n"
            "– 人物眼神清澈有神，表情温和生动，气质朴实亲切\n"
            "– 服装细节精致真实，面料质感通过笔触层叠表现，贴近日常生活\n"
            "– 背景融入自然元素：风吹植物/柔光/云朵/石板街道，营造奇幻生活感\n"
            "– 整体气质：温暖治愈，充满生活诗意，《魔女宅急便》《千与千寻》氛围"
        ),
    },
]


# ── GPT 动态 Prompt 生成 ──

CLOTHING_SYSTEM_PROMPT_TEMPLATE = """\
你是一位时装插画信息图设计师。给定一个城市的天气数据和穿搭建议，
请生成一段完整的信息图生成指令（prompt），用于生成一张时装解析风格的信息图插画。

本次视觉风格：{style_name}
{style_desc}

除上述风格特征外，所有风格通用要求：
– 极简黑色箭头标注与短标签说明
– 背景融入该城市的标志性城市元素（地标建筑、街景轮廓、城市天际线等），以淡化、简笔或半透明方式呈现，不抢主体
– 画面整体氛围反映当天天气状况，通过光影、色调、空气感营造真实天气氛围
– 信息图元素：3-6 个精简标注箭头指向剪裁或材质细节，可选局部材质色块或细节放大插图
– 竖版排版（PORTRAIT），印刷级清晰度，整体精致

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


def _pick_style() -> dict:
    """随机选取一种视觉风格。"""
    return random.choice(VISUAL_STYLES)


async def generate_city_prompt_via_gpt(
    advice: ClothingAdvice,
    gender: str | None = None,
    style: dict | None = None,
) -> str | None:
    """调用 GPT 为指定城市动态生成穿搭 infographic prompt。

    Args:
        style: 从 VISUAL_STYLES 中选取的风格字典；None 时内部随机选取

    Returns:
        完整的 prompt 文本，失败返回 None
    """
    from src.common.config import get_llm_config
    llm = get_llm_config()
    if not llm["api_key"]:
        return None

    selected_style = style or _pick_style()
    system_prompt = CLOTHING_SYSTEM_PROMPT_TEMPLATE.format(
        style_name=selected_style["name"],
        style_desc=selected_style["desc"],
    )

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
                {"role": "system", "content": system_prompt},
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


def _build_fallback_prompt(
    advice: ClothingAdvice,
    gender: str | None = None,
    style: dict | None = None,
) -> str:
    """当 GPT 不可用时的基础回退 prompt。"""
    tips_text = "\n".join(f"- {t}" for t in advice.extra_tips) if advice.extra_tips else "无"
    gender_desc = f"性别倾向：{gender}" if gender else ""
    selected_style = style or _pick_style()
    style_lines = selected_style["desc"].replace("–", "•")

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

【视觉风格指令：{selected_style["name"]}】
{style_lines}
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

        # 每张图随机选取一种视觉风格
        style = _pick_style()
        print(f"    🎨 风格：{style['name']}")

        # 尝试 GPT 动态生成 prompt，失败则回退
        city_prompt = await generate_city_prompt_via_gpt(advice, gender=gender, style=style)
        if city_prompt:
            print(f"    ✨ GPT 动态 prompt ({len(city_prompt)} 字)")
        else:
            city_prompt = _build_fallback_prompt(advice, gender=gender, style=style)
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
