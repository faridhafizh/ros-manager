"""Interval scheduler that runs `run` immediately, then repeats."""

from __future__ import annotations

import signal
import time
from typing import Callable

from .config import AppConfig
from .notify import send_notifications
from .service import run_inventory


class StopScheduler(Exception):
    """Raised internally to break the scheduler loop on stop signal."""


def run_schedule(
    config: AppConfig,
    interval_seconds: int,
    stop_event=None,
    *,
    run_fn: Callable = run_inventory,
    notify_fn: Callable = send_notifications,
    notify_all: bool = False,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Run `run` immediately, then repeat every ``interval_seconds``.

    The first run happens immediately. After each cycle the loop checks the
    stop condition, then sleeps interruptibly. Overlapping cycles are never
    started because each `run` completes before the next sleep.
    """
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    old_handler = signal.signal(signal.SIGTERM, _make_handler(stop_event))
    old_handler_int = signal.signal(signal.SIGINT, _make_handler(stop_event))
    try:
        while True:
            results = run_fn(config, do_check=True, do_backup=True)
            try:
                notify_fn(config, results, notify_all=notify_all)
            except Exception:
                # Notification failure must not abort the scheduler.
                pass
            if stop_event is not None and stop_event.is_set():
                break
            _sleep_interruptible(interval_seconds, stop_event, sleep, now)
    finally:
        signal.signal(signal.SIGTERM, old_handler)
        signal.signal(signal.SIGINT, old_handler_int)


def _make_handler(stop_event):
    def handler(signum, frame):
        if stop_event is not None:
            stop_event.set()
        else:
            raise StopScheduler(signum)
    return handler


def _sleep_interruptible(
    seconds: float,
    stop_event,
    sleep: Callable[[float], None],
    now: Callable[[], float],
) -> None:
    if stop_event is None:
        sleep(seconds)
        return
    deadline = now() + seconds
    while now() < deadline:
        if stop_event.is_set():
            return
        remaining = deadline - now()
        sleep(min(0.25, remaining))
