"""Optional Telegram notifications via the Bot API."""

from __future__ import annotations

import os
from typing import Optional

import httpx

from .models import TelegramConfig


class TelegramError(Exception):
    """Raised when Telegram notification is requested but cannot be sent."""


def resolve_telegram(config) -> Optional[TelegramConfig]:
    """Return Telegram config if enabled, None if disabled, or raise on invalid.

    A telegram block with only one of token_env/chat_id, or a token_env that
    is not present in the environment, is an error for commands that request
    notification.
    """
    telegram = config.telegram
    if telegram is None:
        return None
    if (telegram.token_env is None) != (telegram.chat_id is None):
        raise TelegramError(
            "telegram: token_env and chat_id must be set together"
        )
    if telegram.token_env is None:
        return None
    token = os.environ.get(telegram.token_env)
    if not token or not token.strip():
        raise TelegramError(
            f"telegram: environment variable {telegram.token_env!r} is unset or empty"
        )
    return telegram


def send_summary(telegram: TelegramConfig, chat_id: str, text: str) -> None:
    """Send a text message via Telegram Bot API without logging the token."""
    token = os.environ.get(telegram.token_env, "")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                url,
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise TelegramError(f"Telegram request failed: {exc}") from exc
