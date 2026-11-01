"""Service orchestration tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ros_manager.models import AppConfig, RouterConfig, RouterHealth
from ros_manager.router import RouterError
from ros_manager.service import (
    BackupResult,
    RouterResult,
    RouterSelectionError,
    any_failure,
    backup_router,
    filter_config,
    run_inventory,
    select_routers,
)


def test_run_inventory_partial_failure():
    cfg = AppConfig(
        backup_dir="backups",
        routers=[
            RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P1"),
            RouterConfig(name="r2", host="10.0.0.2", username="a", password_env="P2"),
        ],
    )

    def fake_run_router(config, backup_dir, do_check, do_backup, keep_last=None):
        if config.name == "r1":
            return RouterResult(
                name="r1",
                host="10.0.0.1",
                health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
            )
        return RouterResult(
            name="r2",
            host="10.0.0.2",
            health=RouterHealth(name="r2", host="10.0.0.2", status="error", error="down"),
        )

    with patch("ros_manager.service.run_router", side_effect=fake_run_router):
        results = run_inventory(cfg, do_check=True, do_backup=False)
    assert len(results) == 2
    assert results[0].health.status == "ok"
    assert results[1].health.status == "error"
    assert any_failure(results) is True


def test_any_failure_backup_error():
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
        ),
        RouterResult(
            name="r2",
            host="10.0.0.2",
            backup=BackupResult(name="r2", host="10.0.0.2", status="error", error="ssh fail"),
        ),
    ]
    assert any_failure(results) is True


# -- router selection ----------------------------------------------------


def _routers():
    return [
        RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P"),
        RouterConfig(name="r2", host="10.0.0.2", username="a", password_env="P", groups=("core",)),
        RouterConfig(name="r3", host="10.0.0.3", username="a", password_env="P", groups=("edge", "core")),
    ]


def test_select_routers_no_filter_returns_all():
    assert [r.name for r in select_routers(_routers())] == ["r1", "r2", "r3"]


def test_select_routers_by_name():
    assert [r.name for r in select_routers(_routers(), names=["r1", "r3"])] == ["r1", "r3"]


def test_select_routers_by_group():
    assert [r.name for r in select_routers(_routers(), groups=["core"])] == ["r2", "r3"]


def test_select_routers_implicit_default_group():
    assert [r.name for r in select_routers(_routers(), groups=["default"])] == ["r1"]


def test_select_routers_union_of_filters():
    assert [r.name for r in select_routers(_routers(), names=["r1"], groups=["edge"])] == ["r1", "r3"]


def test_select_routers_unknown_name():
    with pytest.raises(RouterSelectionError, match="unknown router"):
        select_routers(_routers(), names=["nope"])


def test_select_routers_unknown_group():
    with pytest.raises(RouterSelectionError, match="unknown group"):
        select_routers(_routers(), groups=["nope"])


def test_filter_config_returns_copy_with_subset():
    cfg = AppConfig(backup_dir="b", routers=_routers())
    filtered = filter_config(cfg, groups=["edge"])
    assert [r.name for r in filtered.routers] == ["r3"]
    assert len(cfg.routers) == 3  # original untouched


# -- retention -----------------------------------------------------------


def test_backup_router_prunes_old_backups(tmp_path, monkeypatch):
    monkeypatch.setenv("P", "pw")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for stamp in ("20260101T000000.000000Z", "20260102T000000.000000Z", "20260103T000000.000000Z"):
        (backup_dir / f"r1_{stamp}.rsc").write_text("old\n", encoding="utf-8")

    client = MagicMock()
    client.export_config.return_value = "/system identity\n"
    with patch("ros_manager.service.RouterClient", return_value=client):
        result = backup_router(
            RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P"),
            str(backup_dir),
            keep_last=2,
        )

    assert result.status == "ok"
    assert result.pruned == 2  # 3 old + 1 new = 4 files, keep 2
    remaining = sorted(p.name for p in backup_dir.glob("r1_*.rsc"))
    assert len(remaining) == 2
    assert remaining[-1].startswith("r1_2026")


def test_backup_router_failure_does_not_prune(tmp_path, monkeypatch):
    monkeypatch.setenv("P", "pw")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / "r1_20260101T000000.000000Z.rsc"
    old.write_text("old\n", encoding="utf-8")

    client = MagicMock()
    client.export_config.side_effect = RouterError("boom")
    with patch("ros_manager.service.RouterClient", return_value=client):
        result = backup_router(
            RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P"),
            str(backup_dir),
            keep_last=1,
        )

    assert result.status == "error"
    assert old.exists()


def test_backup_router_per_router_retention_override(tmp_path, monkeypatch):
    monkeypatch.setenv("P", "pw")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for stamp in ("20260101T000000.000000Z", "20260102T000000.000000Z", "20260103T000000.000000Z"):
        (backup_dir / f"r1_{stamp}.rsc").write_text("old\n", encoding="utf-8")

    client = MagicMock()
    client.export_config.return_value = "/system identity\n"
    router = RouterConfig(
        name="r1", host="10.0.0.1", username="a", password_env="P", retention_keep_last=1
    )
    with patch("ros_manager.service.RouterClient", return_value=client):
        result = backup_router(router, str(backup_dir), keep_last=10)

    assert result.pruned == 3  # override wins: keep only the new file
    assert len(list(backup_dir.glob("r1_*.rsc"))) == 1
