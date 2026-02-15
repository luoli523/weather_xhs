"""诗词 NotebookLM Pipeline

上传诗词 Markdown → 用 GPT 生成的 prompt 生成 infographic → 下载图片。
"""

from pathlib import Path

from notebooklm import NotebookLMClient

from src.common.notebooklm import find_or_create_notebook, upload_source, create_infographic_with_retry


async def run_pipeline(
    md_file: str,
    prompt: str,
    artifact_name: str,
    output_dir: str,
) -> str | None:
    """诗词 NotebookLM pipeline：上传诗词 Markdown → 生成 infographic → 下载

    Args:
        md_file: 诗词 Markdown 文件路径
        prompt: GPT 动态生成的 infographic prompt
        artifact_name: 生成物命名（如 "诗词_中秋节_2026-09-27"）
        output_dir: 输出目录

    Returns:
        生成的图片文件路径，失败返回 None
    """
    print("\n📜 诗词 NotebookLM Pipeline 开始")

    async with await NotebookLMClient.from_storage() as client:
        print("\n[1/3] 查找 notebook...")
        notebook_id = await find_or_create_notebook(client)

        print("\n[2/3] 上传诗词 source...")
        source_id = await upload_source(client, notebook_id, md_file)

        print("\n[3/3] 生成诗词 infographic...")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        status = await create_infographic_with_retry(
            client, notebook_id, source_id, prompt,
        )
        if not status:
            print("    ❌ 诗词 infographic 创建失败")
            return None

        print(f"    等待生成完成 (task_id={status.task_id[:8]}...)...")
        await client.artifacts.wait_for_completion(
            notebook_id, status.task_id, timeout=300
        )

        await client.artifacts.rename(notebook_id, status.task_id, artifact_name)
        print(f"    已命名: {artifact_name}")

        out_file = str(output_path / f"{artifact_name}.png")
        await client.artifacts.download_infographic(
            notebook_id, out_file, artifact_id=status.task_id
        )
        print(f"    已下载: {out_file}")

        print("\n📜 诗词 NotebookLM Pipeline 完成")
        return out_file
