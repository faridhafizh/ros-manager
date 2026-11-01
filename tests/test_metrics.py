"""SQLite metric history tests."""

from __future__ import annotations

from datetime import datetime, timezone

from ros_manager.metrics import load_history, prune_history, record_snapshot
from ros_manager.models import RouterHealth
from ros_manager.service import RouterResult

TS = "2026-01-01T00:00:00.000000Z"
SINCE = "2025-01-01T00:00:00.000000Z"


def _result(name: str = "r1", **kwargs) -> RouterResult:
    return RouterResult(
        name=name,
        host="10.0.0.1",
        health=RouterHealth(name=name, host="10.0.0.1", status="ok", **kwargs),
    )


def test_record_and_load_history(tmp_path):
    db = tmp_path / "metrics.db"
    record_snapshot(
        db,
        TS,
        [
            _result(
                cpu_load_percent=12.5,
                temperature_c=40,
                memory_free_bytes=100,
                memory_total_bytes=200,
            )
        ],
    )
    series = load_history(db, ["r1"], SINCE)
    assert list(series) == ["r1"]
    point = series["r1"][0]
    assert point["t"] == TS
    assert point["status"] == "ok"
    assert point["cpu"] == 12.5
    assert point["mem_free"] == 100
    assert point["mem_total"] == 200


def test_record_skips_results_without_health(tmp_path):
    db = tmp_path / "metrics.db"
    record_snapshot(db, TS, [RouterResult(name="r1", host="10.0.0.1")])
    assert load_history(db, ["r1"], SINCE)["r1"] == []


def test_load_history_filters_by_since_and_router(tmp_path):
    db = tmp_path / "metrics.db"
    record_snapshot(
        db, "2026-01-01T00:00:00.000000Z", [_result("r1"), _result("r2")]
    )
    record_snapshot(db, "2026-01-02T00:00:00.000000Z", [_result("r1")])

    series = load_history(db, ["r1", "r2"], "2026-01-01T12:00:00.000000Z")
    assert [point["t"] for point in series["r1"]] == [
        "2026-01-02T00:00:00.000000Z"
    ]
    assert series["r2"] == []


def test_history_is_downsampled_but_keeps_last_point(tmp_path):
    db = tmp_path / "metrics.db"
    for index in range(300):
        ts = f"2026-01-01T00:{index // 60:02d}:{index % 60:02d}.000000Z"
        record_snapshot(db, ts, [_result(cpu_load_percent=index)])

    series = load_history(db, ["r1"], SINCE)
    assert 0 < len(series["r1"]) <= 240
    assert series["r1"][-1]["cpu"] == 299


def test_prune_history(tmp_path):
    db = tmp_path / "metrics.db"
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    record_snapshot(db, "2025-01-01T00:00:00.000000Z", [_result()])
    record_snapshot(db, "2026-01-31T00:00:00.000000Z", [_result()])

    assert prune_history(db, max_age_days=30, now=now) == 1
    series = load_history(db, ["r1"], SINCE)
    assert len(series["r1"]) == 1


def test_unusable_database_is_tolerated(tmp_path):
    db = tmp_path / "metrics.db"
    db.mkdir()  # a directory cannot be opened as a database
    record_snapshot(db, TS, [_result()])  # must not raise
    assert load_history(db, ["r1"], SINCE) == {"r1": []}
    assert prune_history(db) == 0
