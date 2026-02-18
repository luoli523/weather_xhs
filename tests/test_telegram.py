"""Integration tests for Telegram and Instagram with mocked HTTP."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.common.telegram import get_telegram_config, send_message


class TestTelegramConfig:

    def test_disabled(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "false")
        assert get_telegram_config() is None

    def test_not_set(self):
        assert get_telegram_config() is None

    def test_enabled_with_values(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        result = get_telegram_config()
        assert result == ("test-token", "12345")

    def test_enabled_missing_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        assert get_telegram_config() is None

    def test_enabled_missing_chat_id(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        assert get_telegram_config() is None


class TestSendMessage:

    @pytest.mark.asyncio
    async def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.common.telegram.httpx.AsyncClient", return_value=mock_client):
            result = await send_message("token", "123", "hello")

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden"
        mock_resp.json.return_value = {"ok": False}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.common.telegram.httpx.AsyncClient", return_value=mock_client):
            result = await send_message("token", "123", "hello")

        assert result is False


class TestInstagramConfig:

    def test_disabled(self, monkeypatch):
        from src.common.instagram import get_ig_config
        monkeypatch.setenv("IG_ENABLED", "false")
        assert get_ig_config() is None

    def test_not_set(self):
        from src.common.instagram import get_ig_config
        assert get_ig_config() is None

    def test_enabled(self, monkeypatch, tmp_path):
        from src.common.instagram import get_ig_config
        session_file = tmp_path / "session.json"
        session_file.write_text("{}")
        monkeypatch.setenv("IG_ENABLED", "true")
        monkeypatch.setenv("IG_USERNAME", "testuser")
        monkeypatch.setenv("IG_PASSWORD", "testpass")
        monkeypatch.setenv("IG_SESSION_PATH", str(session_file))
        config = get_ig_config()
        assert config is not None
        assert config["username"] == "testuser"
