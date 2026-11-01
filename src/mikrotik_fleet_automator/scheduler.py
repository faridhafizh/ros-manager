"""Interval scheduler that runs `run` immediately, then repeats."""

from __future__ import annotations

import signal
import time
from typing import Callable

from .config import AppConfig
from .service import run_inventory
from .telegram import resolve_telegram, send_summary


class StopScheduler(Exception):
    """Raised internally to break the scheduler loop on stop signal."""


def run_schedule(
    config: AppConfig,
    interval_seconds: int,
    stop_event=None,
    *,
    run_fn: Callable = run_inventory,
    send_fn: Callable = send_summary,
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

    telegram = resolve_telegram(config)

    old_handler = signal.signal(signal.SIGTERM, _make_handler(stop_event))
    old_handler_int = signal.signal(signal.SIGINT, _make_handler(stop_event))
    try:
        while True:
            results = run_fn(config, do_check=True, do_backup=True)
            summary = _summarize(results)
            if telegram is not None and telegram.chat_id:
                try:
                    send_fn(telegram, telegram.chat_id, summary)
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


def _summarize(results) -> str:
    lines = [f"*MikroTik run summary* ({len(results)} router(s))"]
    for result in results:
        health = result.health
        backup = result.backup
        h = f"check={health.status}" if health else "check=skipped"
        if health and health.error:
            h += f" ({health.error})"
        b = f"backup={backup.status}" if backup else "backup=skipped"
        if backup and backup.error:
            b += f" ({backup.error})"
        lines.append(f"- {result.name} ({result.host}): {h}, {b}")
    return "\n".join(lines)
