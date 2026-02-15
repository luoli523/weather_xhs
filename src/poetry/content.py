"""诗词内容生成模块

从 GPT 返回的诗词数据构建 Markdown（NotebookLM source）、
小红书笔记内容、Instagram 文案和 Telegram 消息文案。

注意：infographic prompt 由 GPT 动态生成，不在此模块中构建。
"""

from pathlib import Path


# ── Markdown 生成（作为 NotebookLM Source）──


def generate_markdown(poem: dict) -> str:
    """生成诗词介绍 Markdown 文本，用于上传到 NotebookLM 作为 source。"""
    customs_text = "\n".join(f"- {c}" for c in poem.get("customs", []))

    md = f"""# {poem['title']} — {poem['dynasty']}·{poem['author']}

**日期**：{poem.get('date', '')}
**节日/场景**：{poem.get('occasion', '')}
**朝代**：{poem['dynasty']}
**作者**：{poem['author']}

## 诗词全文

{poem['full_text']}

## 诗词赏析

{poem['meaning']}

## 相关风俗与文化

{customs_text}
"""
    return md


def save_markdown(content: str, output_path: str) -> str:
    """保存诗词 Markdown 文件"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return output_path


# ── 小红书笔记内容 ──


def build_xhs_content(poem: dict) -> tuple[str, str, list[str]]:
    """构建诗词小红书笔记的标题、正文和标签。

    Returns:
        (title, content, tags) 三元组
    """
    occasion = poem.get("occasion", "")
    title = f"今日{occasion}｜{poem['title']}"
    if len(title) > 20:
        title = f"{occasion}｜{poem['title']}"[:20]

    lines = []
    lines.append(f"📜 {poem['title']}")
    lines.append(f"    —— {poem['dynasty']}·{poem['author']}")
    lines.append("")
    lines.append(poem["full_text"])
    lines.append("")

    lines.append(f"📖 赏析")
    # 截取赏析前200字避免过长
    meaning = poem["meaning"]
    if len(meaning) > 200:
        meaning = meaning[:200] + "……"
    lines.append(meaning)
    lines.append("")

    if poem.get("customs"):
        lines.append("🎎 风俗知识")
        for custom in poem["customs"][:4]:
            lines.append(f"  • {custom}")

    content = "\n".join(lines)

    tags = [
        poem.get("occasion", ""),
        "唐诗宋词",
        "古典诗词",
        "中国文化",
        "传统文化",
        poem["author"],
        "诗词赏析",
        "文化科普",
    ]
    # 过滤空标签
    tags = [t for t in tags if t]

    return title, content, tags


# ── Instagram 帖子文案 ──


def build_ig_caption(poem: dict) -> str:
    """构建诗词 Instagram 帖子文案。"""
    customs_text = "\n".join(f"  • {c}" for c in poem.get("customs", [])[:4])

    lines = [
        f"📜 {poem['title']}",
        f"    —— {poem['dynasty']}·{poem['author']}",
        "",
        poem["full_text"],
        "",
        f"📖 {poem['meaning'][:200]}",
        "",
    ]

    if customs_text:
        lines.extend([
            "🎎 风俗知识",
            customs_text,
            "",
        ])

    hashtags = " ".join([
        f"#{poem.get('occasion', '')}",
        "#唐诗宋词",
        "#古典诗词",
        "#ChinesePoetry",
        f"#{poem['author']}",
        "#传统文化",
        "#中国文化",
        "#ChineseCulture",
    ])
    lines.append(hashtags)

    return "\n".join(lines)


# ── Telegram 消息文案 ──


def build_telegram_caption(poem: dict) -> str:
    """构建诗词 Telegram 图片说明文案"""
    occasion = poem.get("occasion", "")
    customs_short = "、".join(
        c.split("：")[0] if "：" in c else c[:10]
        for c in poem.get("customs", [])[:3]
    )

    return (
        f"<b>📜 {poem['title']}</b>\n"
        f"    —— {poem['dynasty']}·{poem['author']}\n\n"
        f"🏷 {occasion}\n"
        f"🎎 风俗：{customs_short}\n"
    )
