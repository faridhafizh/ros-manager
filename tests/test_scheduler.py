"""Scheduler tests (no real sleeping)."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from ros_manager import scheduler as sched_module
from ros_manager.models import AppConfig


def test_scheduler_runs_immediately_and_stops(monkeypatch):
    cfg = AppConfig(backup_dir="b", routers=[])
    calls = []
    notified = []

    def fake_run(config, do_check, do_backup):
        calls.append(1)
        return []

    def fake_notify(config, results, *, notify_all=False):
        notified.append(notify_all)

    stop = threading.Event()
    stop.set()  # already stopped: loop should exit after the immediate run
    monkeypatch.setattr(sched_module, "signal", MagicMock())
    sched_module.run_schedule(
        cfg,
        1,
        stop_event=stop,
        run_fn=fake_run,
        notify_fn=fake_notify,
    )
    assert len(calls) == 1  # ran once, then stopped
    assert notified == [False]


def test_scheduler_notification_failure_does_not_abort(monkeypatch):
    cfg = AppConfig(backup_dir="b", routers=[])
    calls = []
    stop = threading.Event()
    stop.set()

    def fake_run(config, do_check, do_backup):
        calls.append(1)
        return []

    def failing_notify(config, results, *, notify_all=False):
        raise RuntimeError("webhook down")

    monkeypatch.setattr(sched_module, "signal", MagicMock())
    sched_module.run_schedule(
        cfg,
        1,
        stop_event=stop,
        run_fn=fake_run,
        notify_fn=failing_notify,
    )
    assert len(calls) == 1
