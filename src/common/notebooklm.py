"""NotebookLM 共享基础功能

提供 notebook 查找/创建、source 上传等通用操作，
供 clothing 和 solar_term 模块复用。
"""

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
