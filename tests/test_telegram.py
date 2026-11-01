"""Telegram notification tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ros_manager import telegram as tg_module
from ros_manager.models import AppConfig, TelegramConfig


def test_resolve_telegram_none_when_disabled():
    cfg = AppConfig(backup_dir="b", routers=[])
    assert tg_module.resolve_telegram(cfg) is None


def test_resolve_telegram_invalid_pair():
    cfg = AppConfig(
        backup_dir="b",
        routers=[],
        telegram=TelegramConfig(token_env="T", chat_id=None),
    )
    with pytest.raises(tg_module.TelegramError, match="together"):
        tg_module.resolve_telegram(cfg)


def test_resolve_telegram_token_missing(monkeypatch):
    monkeypatch.delenv("T", raising=False)
    cfg = AppConfig(
        backup_dir="b",
        routers=[],
        telegram=TelegramConfig(token_env="T", chat_id="123"),
    )
    with pytest.raises(tg_module.TelegramError, match="unset or empty"):
        tg_module.resolve_telegram(cfg)


def test_send_summary_no_token_logged(monkeypatch):
    monkeypatch.setenv("T", "secret-token")
    with patch.object(tg_module.httpx, "Client") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.post.return_value.raise_for_status.return_value = None
        tg_module.send_summary(
            TelegramConfig(token_env="T", chat_id="1"), "chat-1", "hi"
        )
        _, kwargs = instance.post.call_args
        assert "secret-token" not in kwargs["json"]["text"]
