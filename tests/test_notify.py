"""Notification tests: channel resolution, flap detection, state, webhook."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ros_manager import notify as notify_module
from ros_manager.models import (
    AppConfig,
    NotificationsConfig,
    RouterHealth,
    TelegramConfig,
    WebhookConfig,
)
from ros_manager.notify import (
    NotifyError,
    build_full_message,
    changed_router_names,
    compute_statuses,
    load_state,
    resolve_channels,
    save_state,
    send_notifications,
)
from ros_manager.service import BackupResult, RouterResult


def _results(statuses):
    results = []
    for name, status in statuses.items():
        if status == "ok":
            results.append(
                RouterResult(
                    name=name,
                    host=f"10.0.0.{name[-1]}",
                    health=RouterHealth(name=name, host="h", status="ok"),
                    backup=BackupResult(name=name, host="h", status="ok", path=f"/b/{name}.rsc"),
                )
            )
        else:
            results.append(
                RouterResult(
                    name=name,
                    host=f"10.0.0.{name[-1]}",
                    health=RouterHealth(name=name, host="h", status="error", error="timeout"),
                    backup=BackupResult(name=name, host="h", status="skipped"),
                )
            )
    return results


def _config(**kwargs):
    return AppConfig(backup_dir="b", routers=[], **kwargs)


# -- channel resolution --------------------------------------------------


def test_resolve_channels_disabled():
    assert resolve_channels(_config()) == []


def test_resolve_channels_top_level_telegram(monkeypatch):
    monkeypatch.setenv("T", "token")
    cfg = _config(telegram=TelegramConfig(token_env="T", chat_id="1"))
    channels = resolve_channels(cfg)
    assert [c.kind for c in channels] == ["telegram"]


def test_resolve_channels_notifications_telegram(monkeypatch):
    monkeypatch.setenv("T", "token")
    cfg = _config(
        notifications=NotificationsConfig(
            telegram=TelegramConfig(token_env="T", chat_id="1")
        )
    )
    assert [c.kind for c in resolve_channels(cfg)] == ["telegram"]


def test_resolve_channels_webhook(monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    cfg = _config(
        notifications=NotificationsConfig(
            webhook=WebhookConfig(url_env="HOOK", style="slack")
        )
    )
    channels = resolve_channels(cfg)
    assert [c.kind for c in channels] == ["webhook"]
    assert channels[0].webhook.style == "slack"


def test_resolve_channels_webhook_missing_env(monkeypatch):
    monkeypatch.delenv("HOOK", raising=False)
    cfg = _config(notifications=NotificationsConfig(webhook=WebhookConfig(url_env="HOOK")))
    with pytest.raises(NotifyError, match="unset or empty"):
        resolve_channels(cfg)


def test_resolve_channels_telegram_missing_token(monkeypatch):
    monkeypatch.delenv("T", raising=False)
    cfg = _config(notifications=NotificationsConfig(telegram=TelegramConfig(token_env="T", chat_id="1")))
    with pytest.raises(NotifyError, match="unset or empty"):
        resolve_channels(cfg)


# -- status state --------------------------------------------------------


def test_compute_statuses_and_changes():
    results = _results({"r1": "ok", "r2": "error"})
    current = compute_statuses(results)
    assert current["r1"]["status"] == "ok"
    assert current["r2"]["status"] == "error"
    assert changed_router_names({}, current) == ["r1", "r2"]
    assert changed_router_names(current, current) == []
    previous = {"r1": {"status": "error"}, "r2": {"status": "error"}}
    assert changed_router_names(previous, current) == ["r1"]


def test_load_state_missing_and_corrupt(tmp_path):
    assert load_state(tmp_path / "missing.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_state(bad) == {}
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"routers": []}), encoding="utf-8")
    assert load_state(wrong) == {}


def test_save_state_roundtrip(tmp_path):
    path = tmp_path / "nested" / "state.json"
    save_state(path, {"r1": {"status": "ok"}})
    assert load_state(path) == {"r1": {"status": "ok"}}
    assert not (path.parent / (path.name + ".tmp")).exists()


# -- flap-aware sending --------------------------------------------------


def test_first_run_sends_and_persists_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    cfg = _config(
        notifications=NotificationsConfig(webhook=WebhookConfig(url_env="HOOK")),
        state_file=str(tmp_path / "state.json"),
    )
    sent = []
    outcome = send_notifications(
        cfg,
        _results({"r1": "ok"}),
        sender=lambda channel, text: sent.append((channel.kind, text)),
    )
    assert outcome.sent is True
    assert outcome.changed == ["r1"]
    assert sent[0][0] == "webhook"
    assert "new -> ok" in sent[0][1]
    assert load_state(tmp_path / "state.json")["r1"]["status"] == "ok"


def test_unchanged_run_skips_notification(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    cfg = _config(
        notifications=NotificationsConfig(webhook=WebhookConfig(url_env="HOOK")),
        state_file=str(tmp_path / "state.json"),
    )
    send_notifications(cfg, _results({"r1": "ok"}), sender=lambda c, t: None)
    sent = []
    outcome = send_notifications(
        cfg,
        _results({"r1": "ok"}),
        sender=lambda channel, text: sent.append(text),
    )
    assert outcome.sent is False
    assert outcome.skipped_reason == "no status changes"
    assert sent == []


def test_status_change_sends_alert(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    cfg = _config(
        notifications=NotificationsConfig(webhook=WebhookConfig(url_env="HOOK")),
        state_file=str(tmp_path / "state.json"),
    )
    send_notifications(cfg, _results({"r1": "ok"}), sender=lambda c, t: None)
    sent = []
    outcome = send_notifications(
        cfg,
        _results({"r1": "error"}),
        sender=lambda channel, text: sent.append(text),
    )
    assert outcome.sent is True
    assert outcome.changed == ["r1"]
    assert "ok -> error" in sent[0]
    assert "timeout" in sent[0]


def test_notify_all_sends_full_summary_even_without_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    cfg = _config(
        notifications=NotificationsConfig(webhook=WebhookConfig(url_env="HOOK")),
        state_file=str(tmp_path / "state.json"),
    )
    send_notifications(cfg, _results({"r1": "ok"}), sender=lambda c, t: None)
    sent = []
    outcome = send_notifications(
        cfg,
        _results({"r1": "ok"}),
        notify_all=True,
        sender=lambda channel, text: sent.append(text),
    )
    assert outcome.sent is True
    assert "run summary" in sent[0]


def test_notifications_disabled_is_noop(tmp_path):
    cfg = _config(state_file=str(tmp_path / "state.json"))
    outcome = send_notifications(cfg, _results({"r1": "ok"}))
    assert outcome.sent is False
    assert outcome.skipped_reason == "notifications disabled"


def test_invalid_config_raises_even_without_changes(tmp_path, monkeypatch):
    monkeypatch.delenv("T", raising=False)
    cfg = _config(
        notifications=NotificationsConfig(telegram=TelegramConfig(token_env="T", chat_id="1")),
        state_file=str(tmp_path / "state.json"),
    )
    with pytest.raises(NotifyError):
        send_notifications(cfg, _results({"r1": "ok"}))


# -- webhook payloads ----------------------------------------------------


def test_webhook_discord_payload(monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    webhook = WebhookConfig(url_env="HOOK", style="discord")
    with patch.object(notify_module.httpx, "Client") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.post.return_value.raise_for_status.return_value = None
        notify_module._send_webhook(webhook, "hello")
        _, kwargs = instance.post.call_args
        assert kwargs["json"] == {"content": "hello"}


def test_webhook_generic_payload(monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    webhook = WebhookConfig(url_env="HOOK", style="generic")
    with patch.object(notify_module.httpx, "Client") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.post.return_value.raise_for_status.return_value = None
        notify_module._send_webhook(webhook, "hello")
        _, kwargs = instance.post.call_args
        assert kwargs["json"] == {"text": "hello"}


def test_full_message_contains_each_router():
    text = build_full_message(_results({"r1": "ok", "r2": "error"}))
    assert "r1" in text and "r2" in text
    assert "2 router(s)" in text
