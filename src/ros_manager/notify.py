"""Multi-channel notifications with flap detection.

Channels are configured under ``notifications:`` (Telegram and/or a generic
webhook). Router status is persisted in a small JSON state file so a message
is only sent when a router changes between ``ok`` and ``error``; pass
``notify_all=True`` to force a full summary.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx

from .models import (
    AppConfig,
    NotificationsConfig,
    TelegramConfig,
    WebhookConfig,
)
from .service import RouterResult
from . import telegram as telegram_module


class NotifyError(Exception):
    """Raised when notifications are requested but cannot be delivered."""


@dataclass(frozen=True)
class Channel:
    """A resolved notification channel ready to send."""

    kind: str  # "telegram" | "webhook"
    telegram: Optional[TelegramConfig] = None
    webhook: Optional[WebhookConfig] = None


@dataclass(frozen=True)
class NotifyOutcome:
    """What happened when notifications were evaluated."""

    sent: bool
    changed: list[str]
    skipped_reason: Optional[str] = None


# -- configuration -------------------------------------------------------


def _telegram_settings(config: AppConfig) -> Optional[TelegramConfig]:
    notifications: Optional[NotificationsConfig] = config.notifications
    if notifications is not None and notifications.telegram is not None:
        return notifications.telegram
    return config.telegram


def resolve_channels(config: AppConfig) -> list[Channel]:
    """Resolve configured channels; raises NotifyError on invalid setup."""
    channels: list[Channel] = []

    telegram = _telegram_settings(config)
    if telegram is not None:
        if (telegram.token_env is None) != (telegram.chat_id is None):
            raise NotifyError(
                "telegram: token_env and chat_id must be set together"
            )
        if telegram.token_env is not None:
            token = os.environ.get(telegram.token_env, "")
            if not token.strip():
                raise NotifyError(
                    f"telegram: environment variable {telegram.token_env!r} "
                    "is unset or empty"
                )
            channels.append(Channel(kind="telegram", telegram=telegram))

    webhook = config.notifications.webhook if config.notifications else None
    if webhook is not None:
        url = os.environ.get(webhook.url_env, "")
        if not url.strip():
            raise NotifyError(
                f"webhook: environment variable {webhook.url_env!r} "
                "is unset or empty"
            )
        channels.append(Channel(kind="webhook", webhook=webhook))

    return channels


# -- status state --------------------------------------------------------


def _result_status(result: RouterResult) -> str:
    if result.health is not None and result.health.status == "error":
        return "error"
    if result.backup is not None and result.backup.status == "error":
        return "error"
    return "ok"


def compute_statuses(results: list[RouterResult]) -> dict[str, dict]:
    """Return the current status snapshot keyed by router name."""
    statuses: dict[str, dict] = {}
    for result in results:
        statuses[result.name] = {
            "status": _result_status(result),
            "check": result.health.status if result.health else "skipped",
            "backup": result.backup.status if result.backup else "skipped",
        }
    return statuses


def load_state(path: str | Path) -> dict[str, dict]:
    """Load the previous status map; missing or corrupt state means empty."""
    try:
        with Path(path).open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    routers = data.get("routers")
    if not isinstance(routers, dict):
        return {}
    return {
        str(name): value
        for name, value in routers.items()
        if isinstance(value, dict)
    }


def save_state(path: str | Path, statuses: dict[str, dict]) -> None:
    """Persist the current status map atomically."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "routers": statuses}
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def changed_router_names(
    previous: dict[str, dict], current: dict[str, dict]
) -> list[str]:
    """Names whose overall status differs from the previous snapshot."""
    changed: list[str] = []
    for name, status in current.items():
        before = previous.get(name, {}).get("status")
        if before != status.get("status"):
            changed.append(name)
    return changed


# -- message building ----------------------------------------------------


def _detail(result: RouterResult) -> str:
    parts = []
    if result.health is not None:
        text = f"check={result.health.status}"
        if result.health.error:
            text += f" ({result.health.error})"
        parts.append(text)
    else:
        parts.append("check=skipped")
    if result.backup is not None:
        text = f"backup={result.backup.status}"
        if result.backup.error:
            text += f" ({result.backup.error})"
        parts.append(text)
    else:
        parts.append("backup=skipped")
    return ", ".join(parts)


def build_full_message(results: list[RouterResult]) -> str:
    lines = [f"*ROS Manager run summary* ({len(results)} router(s))"]
    for result in results:
        lines.append(f"- {result.name} ({result.host}): {_detail(result)}")
    return "\n".join(lines)


def build_change_message(
    results: list[RouterResult],
    previous: dict[str, dict],
    current: dict[str, dict],
    changed: list[str],
) -> str:
    changed_set = set(changed)
    lines = [f"*ROS Manager alert* ({len(changed)} router(s) changed)"]
    for result in results:
        if result.name not in changed_set:
            continue
        before = previous.get(result.name, {}).get("status", "new")
        after = current.get(result.name, {}).get("status", "unknown")
        lines.append(
            f"- {result.name} ({result.host}): {before} -> {after} "
            f"({_detail(result)})"
        )
    return "\n".join(lines)


# -- sending -------------------------------------------------------------


def _send_webhook(webhook: WebhookConfig, text: str) -> None:
    url = os.environ.get(webhook.url_env, "")
    if not url.strip():
        raise NotifyError(
            f"webhook: environment variable {webhook.url_env!r} is unset or empty"
        )
    payload = {"content": text} if webhook.style == "discord" else {"text": text}
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            raise NotifyError(
                f"webhook request failed with HTTP {exc.response.status_code}"
            ) from exc
        raise NotifyError(
            f"webhook request failed ({type(exc).__name__})"
        ) from exc


def _default_sender(channel: Channel, text: str) -> None:
    if channel.kind == "telegram":
        telegram = channel.telegram
        if telegram is None or telegram.chat_id is None:
            raise NotifyError("telegram: missing channel configuration")
        telegram_module.send_summary(telegram, telegram.chat_id, text)
        return
    if channel.kind == "webhook":
        if channel.webhook is None:
            raise NotifyError("webhook: missing channel configuration")
        _send_webhook(channel.webhook, text)
        return
    raise NotifyError(f"unknown notification channel: {channel.kind}")


Sender = Callable[[Channel, str], None]


def send_notifications(
    config: AppConfig,
    results: list[RouterResult],
    *,
    notify_all: bool = False,
    state_path: str | Path | None = None,
    sender: Optional[Sender] = None,
) -> NotifyOutcome:
    """Send a flap-aware notification summary.

    A message is sent only when at least one router changed status, unless
    ``notify_all`` is set. Invalid configuration raises NotifyError even when
    nothing changed, so misconfiguration is never silently ignored.
    """
    channels = resolve_channels(config)
    if not channels:
        return NotifyOutcome(
            sent=False, changed=[], skipped_reason="notifications disabled"
        )

    state_file = Path(state_path) if state_path is not None else Path(config.state_file)
    previous = load_state(state_file)
    current = compute_statuses(results)
    changed = changed_router_names(previous, current)

    if not changed and not notify_all:
        save_state(state_file, current)
        return NotifyOutcome(
            sent=False, changed=[], skipped_reason="no status changes"
        )

    if notify_all:
        text = build_full_message(results)
    else:
        text = build_change_message(results, previous, current, changed)

    send = sender or _default_sender
    for channel in channels:
        send(channel, text)

    save_state(state_file, current)
    return NotifyOutcome(sent=True, changed=changed)
