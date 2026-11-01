"""SQLite-backed metric history for the dashboard trend charts.

Every live status check appends one row per router to a small SQLite file.
The store is best-effort: a locked, missing, or corrupt database never fails
the status check that is recording it.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

from .service import RouterResult

log = logging.getLogger(__name__)

#: Rows older than this are pruned when the dashboard server starts.
MAX_AGE_DAYS = 30

#: Maximum number of points returned per router, to keep the payload small.
MAX_POINTS = 240

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    ts TEXT NOT NULL,
    router TEXT NOT NULL,
    status TEXT,
    temperature_c REAL,
    cpu_load_percent REAL,
    memory_free_bytes INTEGER,
    memory_total_bytes INTEGER,
    interfaces_up INTEGER,
    interfaces_total INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snapshots_router_ts
    ON snapshots (router, ts);
"""


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    conn.executescript(_SCHEMA)
    return conn


def record_snapshot(
    db_path: str | Path, ts: str, results: Iterable[RouterResult]
) -> None:
    """Append one history row per router that actually produced a health check."""
    rows: list[tuple] = []
    for result in results:
        health = result.health
        if health is None:
            continue
        up = total = None
        if health.interfaces is not None:
            total = len(health.interfaces)
            up = sum(1 for iface in health.interfaces if iface.running is True)
        rows.append(
            (
                ts,
                result.name,
                health.status,
                health.temperature_c,
                health.cpu_load_percent,
                health.memory_free_bytes,
                health.memory_total_bytes,
                up,
                total,
            )
        )
    if not rows:
        return
    try:
        conn = _connect(db_path)
        try:
            conn.executemany(
                "INSERT INTO snapshots (ts, router, status, temperature_c, "
                "cpu_load_percent, memory_free_bytes, memory_total_bytes, "
                "interfaces_up, interfaces_total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.commit()
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:  # pragma: no cover - defensive
        log.warning("could not record metric snapshot: %s", exc)


def _downsample(points: list[dict], limit: int = MAX_POINTS) -> list[dict]:
    if len(points) <= limit:
        return points
    step = len(points) / limit
    sampled = [points[int(index * step)] for index in range(limit)]
    if sampled[-1] is not points[-1]:
        sampled[-1] = points[-1]
    return sampled


def load_history(
    db_path: str | Path,
    router_names: Iterable[str],
    since: str,
) -> dict[str, list[dict]]:
    """Return ``{router: [points]}`` for snapshots at or after ``since``."""
    names = list(router_names)
    series: dict[str, list[dict]] = {name: [] for name in names}
    if not names:
        return series

    placeholders = ", ".join("?" for _ in names)
    query = (
        "SELECT ts, router, status, cpu_load_percent, memory_free_bytes, "
        "memory_total_bytes FROM snapshots "
        f"WHERE ts >= ? AND router IN ({placeholders}) ORDER BY ts"
    )
    try:
        conn = _connect(db_path)
        try:
            rows = conn.execute(query, [since, *names]).fetchall()
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:  # pragma: no cover - defensive
        log.warning("could not read metric history: %s", exc)
        return series

    for ts, router, status, cpu, mem_free, mem_total in rows:
        if router not in series:
            continue
        series[router].append(
            {
                "t": ts,
                "status": status,
                "cpu": cpu,
                "mem_free": mem_free,
                "mem_total": mem_total,
            }
        )
    return {name: _downsample(points) for name, points in series.items()}


def prune_history(
    db_path: str | Path,
    max_age_days: int = MAX_AGE_DAYS,
    now: Optional[datetime] = None,
) -> int:
    """Delete rows older than ``max_age_days``; returns the number removed."""
    cutoff = _iso((now or datetime.now(timezone.utc)) - timedelta(days=max_age_days))
    try:
        conn = _connect(db_path)
        try:
            cursor = conn.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:  # pragma: no cover - defensive
        log.warning("could not prune metric history: %s", exc)
        return 0
