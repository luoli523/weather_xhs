"""Smoke test: run full pipeline in mock mode to verify orchestration."""

import os
import pytest
import subprocess
import sys


class TestPipelineSmoke:
    """End-to-end smoke tests running main.py with --mock."""

    def _run_main(self, extra_args: list[str], timeout: int = 30, extra_env: dict | None = None):
        """Helper to run main.py in a subprocess with isolated env.

        Explicitly disables all external services to prevent real API calls.
        """
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": ".",
            "HOME": os.environ.get("HOME", "/tmp"),
            "LLM_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key-for-smoke",
            "TELEGRAM_ENABLED": "false",
            "IG_ENABLED": "false",
            "XHS_ENABLED": "false",
        }
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, "main.py"] + extra_args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    def test_mock_no_nlm(self):
        """Pipeline runs with mock weather + no NotebookLM + no publishing."""
        result = self._run_main(["--mock", "--no-nlm", "--no-ig"])
        assert result.returncode == 0, f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        assert "Mock" in result.stdout or "穿搭" in result.stdout

    def test_missing_llm_key_exits_early(self):
        """Without LLM API Key, pipeline should exit early."""
        result = self._run_main(
            ["--mock", "--no-nlm", "--no-ig"],
            extra_env={"OPENAI_API_KEY": ""},
        )
        assert "LLM API Key 未配置" in result.stdout

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "main.py", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--mock" in result.stdout
        assert "--no-nlm" in result.stdout
        assert "--no-ig" in result.stdout
