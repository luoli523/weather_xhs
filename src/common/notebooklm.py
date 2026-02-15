"""NotebookLM 共享基础功能

提供 notebook 查找/创建、source 上传、infographic 创建（含重试）等通用操作，
供 clothing、solar_term 和 poetry 模块复用。
"""

import asyncio
from pathlib import Path

from notebooklm import NotebookLMClient, InfographicOrientation, InfographicDetail

NOTEBOOK_TITLE = "weather_xhs"


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


async def create_infographic_with_retry(
    client: NotebookLMClient,
    notebook_id: str,
    source_id: str,
    prompt: str,
    max_retries: int = 3,
):
    """创建 infographic，带重试逻辑。

    Returns:
        status 对象（含 task_id），全部失败返回 None
    """
    for attempt in range(max_retries):
        try:
            status = await client.artifacts.generate_infographic(
                notebook_id,
                source_ids=[source_id],
                instructions=prompt,
                orientation=InfographicOrientation.PORTRAIT,
                detail_level=InfographicDetail.DETAILED,
                language="zh",
            )
            if status and hasattr(status, "task_id") and status.task_id and len(status.task_id) > 5:
                return status
        except Exception as e:
            print(f"    ⚠ 生成请求失败 (第{attempt+1}次): {e}")

        if attempt < max_retries - 1:
            wait_sec = 10 * (attempt + 1)
            print(f"    ⏳ 等待 {wait_sec}s 后重试...")
            await asyncio.sleep(wait_sec)

    return None
