"""Tests for NotebookLM transient failure handling."""

import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


class RPCTimeoutError(Exception):
    """Fake notebooklm RPCTimeoutError for local tests."""


class SourceAddError(Exception):
    """Fake notebooklm SourceAddError for local tests."""


@pytest.fixture
def notebooklm_modules(monkeypatch):
    """Install a small fake notebooklm module before importing project modules."""
    notebooklm = types.ModuleType("notebooklm")
    notebooklm.NotebookLMClient = object
    notebooklm.InfographicOrientation = SimpleNamespace(PORTRAIT="portrait")
    notebooklm.InfographicDetail = SimpleNamespace(DETAILED="detailed")

    exceptions = types.ModuleType("notebooklm.exceptions")
    exceptions.RPCTimeoutError = RPCTimeoutError
    exceptions.SourceAddError = SourceAddError

    monkeypatch.setitem(sys.modules, "notebooklm", notebooklm)
    monkeypatch.setitem(sys.modules, "notebooklm.exceptions", exceptions)
    sys.modules.pop("src.common.notebooklm", None)
    sys.modules.pop("src.clothing.notebooklm", None)

    yield

    sys.modules.pop("src.common.notebooklm", None)
    sys.modules.pop("src.clothing.notebooklm", None)


@pytest.mark.asyncio
async def test_upload_source_retries_source_add_error(notebooklm_modules, monkeypatch, tmp_path):
    common = importlib.import_module("src.common.notebooklm")
    monkeypatch.setattr(common.asyncio, "sleep", AsyncMock())

    md_file = tmp_path / "guide.md"
    md_file.write_text("# guide\n")

    class FakeSources:
        def __init__(self):
            self.add_calls = 0
            self.deleted_ids = []

        async def list(self, notebook_id):
            return [SimpleNamespace(id="old-source", title="guide.md")]

        async def delete(self, notebook_id, source_id):
            self.deleted_ids.append(source_id)

        async def add_file(self, notebook_id, filename, wait):
            self.add_calls += 1
            if self.add_calls == 1:
                raise SourceAddError("Failed to get SOURCE_ID from registration response")
            return SimpleNamespace(id="new-source", title=Path(filename).name)

    client = SimpleNamespace(sources=FakeSources())

    source_id = await common.upload_source(client, "notebook-1", str(md_file))

    assert source_id == "new-source"
    assert client.sources.add_calls == 2
    assert client.sources.deleted_ids == ["old-source", "old-source"]


@pytest.mark.asyncio
async def test_city_timeout_skips_failed_city_and_continues(
    notebooklm_modules, monkeypatch, sample_advices, tmp_path
):
    clothing = importlib.import_module("src.clothing.notebooklm")
    common = importlib.import_module("src.common.notebooklm")
    monkeypatch.setattr(common.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(clothing.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(clothing, "INFOGRAPHIC_INTERVAL", 0)
    monkeypatch.setattr(clothing, "generate_city_prompt_via_gpt", AsyncMock(return_value=None))

    created_tasks = []

    async def fake_create_infographic(client, notebook_id, source_id, prompt):
        task_id = f"task-{len(created_tasks)}"
        created_tasks.append(task_id)
        return SimpleNamespace(task_id=task_id)

    monkeypatch.setattr(clothing, "create_infographic_with_retry", fake_create_infographic)

    class FakeArtifacts:
        def __init__(self):
            self.wait_calls = []
            self.downloaded_files = []

        async def wait_for_completion(self, notebook_id, task_id, timeout):
            self.wait_calls.append(task_id)
            if task_id == "task-0":
                raise RPCTimeoutError("Request timed out calling LIST_ARTIFACTS")

        async def rename(self, notebook_id, task_id, artifact_name):
            pass

        async def download_infographic(self, notebook_id, out_file, artifact_id):
            self.downloaded_files.append(out_file)

    client = SimpleNamespace(artifacts=FakeArtifacts())

    files = await clothing.generate_city_infographics(
        client,
        "notebook-1",
        "source-1",
        sample_advices,
        str(tmp_path),
    )

    assert len(files) == len(sample_advices) - 1
    assert files == client.artifacts.downloaded_files
    assert client.artifacts.wait_calls.count("task-0") == 3


@pytest.mark.asyncio
async def test_all_city_failures_raise_error(notebooklm_modules, monkeypatch, sample_advices, tmp_path):
    clothing = importlib.import_module("src.clothing.notebooklm")
    monkeypatch.setattr(clothing.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(clothing, "INFOGRAPHIC_INTERVAL", 0)
    monkeypatch.setattr(clothing, "generate_city_prompt_via_gpt", AsyncMock(return_value=None))

    async def fake_create_infographic(client, notebook_id, source_id, prompt):
        return None

    monkeypatch.setattr(clothing, "create_infographic_with_retry", fake_create_infographic)

    client = SimpleNamespace(artifacts=SimpleNamespace())

    with pytest.raises(RuntimeError, match="未成功生成任何穿搭图片"):
        await clothing.generate_city_infographics(
            client,
            "notebook-1",
            "source-1",
            sample_advices,
            str(tmp_path),
        )
