"""节气内容生成模块

生成节气相关的 Markdown（NotebookLM source）、NotebookLM prompt、
小红书笔记内容和 Telegram 消息文案。
"""

from pathlib import Path

import yaml


# ── Markdown 生成（作为 NotebookLM Source）──


def generate_markdown(term: dict) -> str:
    """生成节气介绍 Markdown 文本，用于上传到 NotebookLM 作为 source。"""
    customs_text = "\n".join(f"- {c}" for c in term["customs"])

    md = f"""# {term['name']} — 二十四节气

**日期**：{term['date']}
**季节**：{term['season']}季
**含义**：{term['meaning']}

## 节气介绍

{term['description']}

## 传统习俗

{customs_text}

## 节气饮食

{term['food']}

## 养生提示

{term['health_tip']}
"""
    return md


def save_markdown(content: str, output_path: str) -> str:
    """保存节气 Markdown 文件"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


# ── NotebookLM Prompt ──


def load_prompt(config_path: str = "config/prompts.yaml") -> str:
    """加载节气 infographic prompt 模板"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["solar_term_prompt"]


def build_prompt(term: dict) -> str:
    """用节气信息填充 prompt 模板"""
    template = load_prompt()
    customs_text = "、".join(term["customs"][:4])

    return template.format(
        name=term["name"],
        date=term["date"],
        season=term["season"],
        meaning=term["meaning"],
        description=term["description"],
        customs=customs_text,
        food=term["food"],
        health_tip=term["health_tip"],
    )


# ── 小红书笔记内容 ──


def build_xhs_content(term: dict) -> tuple[str, str, list[str]]:
    """构建节气小红书笔记的标题、正文和标签。

    Returns:
        (title, content, tags) 三元组
    """
    title = f"今日{term['name']}｜{term['season']}季养生指南"
    if len(title) > 20:
        title = title[:20]

    lines = []
    lines.append(f"🌿 今日{term['name']}（{term['date']}）")
    lines.append("")
    lines.append(f"📖 {term['meaning']}")
    lines.append("")
    lines.append(term["description"])
    lines.append("")

    lines.append("🎎 传统习俗")
    for custom in term["customs"]:
        lines.append(f"  • {custom}")
    lines.append("")

    lines.append(f"🍽 节气美食：{term['food']}")
    lines.append("")

    lines.append(f"💆 养生贴士：{term['health_tip']}")

    content = "\n".join(lines)

    tags = [
        term["name"],
        "二十四节气",
        "节气",
        f"{term['season']}季养生",
        "传统文化",
        "中国节气",
        "养生",
        "节气美食",
    ]

    return title, content, tags


# ── Instagram 帖子文案 ──


def build_ig_caption(term: dict) -> str:
    """构建节气 Instagram 帖子文案。"""
    customs_text = "\n".join(f"  • {c}" for c in term["customs"])

    lines = [
        f"🌿 今日{term['name']}（{term['date']}）",
        "",
        f"📖 {term['meaning']}",
        "",
        term["description"],
        "",
        "🎎 传统习俗",
        customs_text,
        "",
        f"🍽 节气美食：{term['food']}",
        "",
        f"💆 养生贴士：{term['health_tip']}",
        "",
        " ".join([
            f"#{term['name']}",
            "#二十四节气",
            "#节气",
            "#SolarTerms",
            f"#{term['season']}季养生",
            "#传统文化",
            "#中国节气",
            "#养生",
            "#ChineseCulture",
        ]),
    ]

    return "\n".join(lines)


# ── Telegram 消息文案 ──


def build_telegram_caption(term: dict) -> str:
    """构建节气 Telegram 图片说明文案"""
    customs_short = "、".join(term["customs"][:3])
    return (
        f"<b>🌿 今日{term['name']}</b>\n\n"
        f"📖 {term['meaning']}\n"
        f"🎎 习俗：{customs_short}\n"
        f"🍽 美食：{term['food']}\n"
        f"💆 养生：{term['health_tip']}"
    )
