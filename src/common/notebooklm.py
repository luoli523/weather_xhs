"""NotebookLM 共享基础功能

提供 notebook 查找/创建、source 上传、infographic 创建（含重试）等通用操作，
供 clothing、solar_term 和 poetry 模块复用。
"""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

import httpx
from notebooklm import NotebookLMClient, InfographicOrientation, InfographicDetail
from notebooklm.exceptions import RPCTimeoutError, SourceAddError

NOTEBOOK_TITLE = "weather_xhs"
NOTEBOOKLM_RETRY_DELAYS = (10, 30, 60)
NOTEBOOKLM_TRANSIENT_ERRORS = (
    RPCTimeoutError,
    SourceAddError,
    httpx.TimeoutException,
    httpx.TransportError,
    TimeoutError,
)

T = TypeVar("T")


async def retry_notebooklm_operation(
    operation_name: str,
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    delays: tuple[float, ...] = NOTEBOOKLM_RETRY_DELAYS,
) -> T:
    """Run a NotebookLM operation with retries for transient service/network errors."""
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except NOTEBOOKLM_TRANSIENT_ERRORS as e:
            err_type = type(e).__name__
            if attempt >= attempts:
                print(f"  ❌ {operation_name} 连续失败 {attempts} 次: [{err_type}] {e}")
                raise

            wait_sec = delays[min(attempt - 1, len(delays) - 1)]
            print(f"  ⚠ {operation_name} 失败 (第{attempt}/{attempts}次): [{err_type}] {e}")
            print(f"  ⏳ 等待 {wait_sec}s 后重试...")
            await asyncio.sleep(wait_sec)

    raise RuntimeError(f"{operation_name} retry loop ended unexpectedly")


async def check_auth() -> bool:
    """检测 NotebookLM 认证是否有效。

    尝试创建客户端并列出 notebook，成功返回 True，失败返回 False。
    """
    try:
        async with await NotebookLMClient.from_storage() as client:
            await client.notebooks.list()
            return True
    except FileNotFoundError:
        print("  ⚠ NotebookLM storage_state.json 不存在")
        return False
    except Exception as e:
        print(f"  ⚠ NotebookLM 认证失败: {type(e).__name__}: {e}")
        return False


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

    async def _upload_once() -> str:
        # 每次重试前重新清理同名 source，处理半成功注册留下的残留。
        existing_sources = await client.sources.list(notebook_id)
        for src in existing_sources:
            if src.title == file_name:
                print(f"  发现同名 source: {file_name}，正在删除旧版本...")
                await client.sources.delete(notebook_id, src.id)

        print(f"  正在上传: {file_name}")
        source = await client.sources.add_file(notebook_id, str(file_path), wait=True)
        print(f"  上传完成: source_id={source.id[:8]}... title={source.title}")
        return source.id

    return await retry_notebooklm_operation(f"上传 source {file_name}", _upload_once)


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
            print(f"    ⚠ 返回无效 status (第{attempt+1}次): {status}")
        except Exception as e:
            err_type = type(e).__name__
            err_cause = f" <- {type(e.__cause__).__name__}: {e.__cause__}" if e.__cause__ else ""
            print(f"    ⚠ 生成请求失败 (第{attempt+1}次): [{err_type}] {e}{err_cause}")

        if attempt < max_retries - 1:
            wait_sec = 10 * (attempt + 1)
            print(f"    ⏳ 等待 {wait_sec}s 后重试...")
            await asyncio.sleep(wait_sec)

    return None
