"""Verify and restore tests (no real routers or SSH)."""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ros_manager.cli import app as cli_app
from ros_manager.config import load_config
from ros_manager.models import AppConfig, RouterConfig
from ros_manager.restore import (
    RestoreError,
    apply_restore,
    plan_restore,
    verify_backup_file,
)

runner = CliRunner()


# -- verify --------------------------------------------------------------


def test_verify_valid_file(tmp_path):
    path = tmp_path / "r1.rsc"
    path.write_text("/interface bridge\n/ip address\n", encoding="utf-8")
    assert verify_backup_file(path) == []


def test_verify_empty_file(tmp_path):
    path = tmp_path / "r1.rsc"
    path.write_text("   \n", encoding="utf-8")
    problems = verify_backup_file(path)
    assert "file is empty" in problems
    assert any("no RouterOS" in p for p in problems)


def test_verify_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        verify_backup_file(tmp_path / "nope.rsc")


def test_verify_non_utf8(tmp_path):
    path = tmp_path / "r1.rsc"
    path.write_bytes(b"\xff\xfe\x00\x00")
    with pytest.raises(UnicodeDecodeError):
        verify_backup_file(path)


def test_verify_no_sections(tmp_path):
    path = tmp_path / "r1.rsc"
    path.write_text("just some text\n", encoding="utf-8")
    problems = verify_backup_file(path)
    assert any("no RouterOS" in p for p in problems)


def test_verify_max_age(tmp_path):
    path = tmp_path / "r1.rsc"
    path.write_text("/interface\n", encoding="utf-8")
    old = time.time() - 40 * 86400
    os.utime(path, (old, old))
    problems = verify_backup_file(path, max_age_days=30)
    assert any("days old" in p for p in problems)
    assert verify_backup_file(path, max_age_days=60) == []


# -- restore planning ----------------------------------------------------


def _config(tmp_path, routers=None):
    return AppConfig(
        backup_dir=str(tmp_path / "backups"),
        routers=routers
        or [RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P")],
    )


def test_plan_restore_unknown_router(tmp_path):
    cfg = _config(tmp_path)
    with pytest.raises(RestoreError, match="unknown router"):
        plan_restore(cfg, "nope", tmp_path / "x.rsc")


def test_plan_restore_missing_file(tmp_path):
    cfg = _config(tmp_path)
    with pytest.raises(RestoreError, match="not found"):
        plan_restore(cfg, "r1", tmp_path / "nope.rsc")


def test_plan_restore_builds_diff_against_latest(tmp_path):
    cfg = _config(tmp_path)
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "r1_20260101T000000.000000Z.rsc").write_text("/interface\n", encoding="utf-8")
    new = tmp_path / "new.rsc"
    new.write_text("/interface\n/ip address\n", encoding="utf-8")

    plan = plan_restore(cfg, "r1", new)

    assert plan.size > 0
    assert plan.latest is not None
    assert plan.latest.name.startswith("r1_")
    assert "+++" in plan.diff
    assert plan.preview == ["/interface", "/ip address"]


def test_plan_restore_without_previous_backup(tmp_path):
    cfg = _config(tmp_path)
    new = tmp_path / "new.rsc"
    new.write_text("/interface\n", encoding="utf-8")
    plan = plan_restore(cfg, "r1", new)
    assert plan.latest is None
    assert plan.diff == ""


# -- restore apply -------------------------------------------------------


def _router():
    return RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P")


def test_apply_restore_uploads_and_imports(tmp_path, monkeypatch):
    monkeypatch.setenv("P", "pw")
    path = tmp_path / "r1.rsc"
    path.write_text("/interface\n", encoding="utf-8")

    client = MagicMock()
    sftp = MagicMock()
    client.open_sftp.return_value = sftp
    stdout = MagicMock()
    stdout.read.return_value = b"imported\n"
    stdout.channel.recv_exit_status.return_value = 0
    client.exec_command.return_value = (MagicMock(), stdout, MagicMock())

    with patch("ros_manager.restore._connect", return_value=client):
        remote = apply_restore(_router(), path)

    sftp.put.assert_called_once()
    assert sftp.put.call_args.args[0] == str(path)
    assert remote.startswith("rosm-restore-") and remote.endswith(".rsc")
    command = client.exec_command.call_args.args[0]
    assert command == f"/import file={remote}"
    client.close.assert_called_once()


def test_apply_restore_import_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("P", "pw")
    path = tmp_path / "r1.rsc"
    path.write_text("/interface\n", encoding="utf-8")

    client = MagicMock()
    client.open_sftp.return_value = MagicMock()
    stdout = MagicMock()
    stdout.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 1
    stderr = MagicMock()
    stderr.read.return_value = b"bad script"
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    with patch("ros_manager.restore._connect", return_value=client):
        with pytest.raises(RestoreError, match="bad script"):
            apply_restore(_router(), path)
    client.close.assert_called_once()


# -- CLI -----------------------------------------------------------------


def test_cli_verify_ok(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    path = tmp_path / "r1.rsc"
    path.write_text("/interface\n", encoding="utf-8")
    result = runner.invoke(cli_app, ["verify", str(path)])
    assert result.exit_code == 0
    assert "ok" in result.output


def test_cli_verify_invalid(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    path = tmp_path / "r1.rsc"
    path.write_text("nothing here\n", encoding="utf-8")
    result = runner.invoke(cli_app, ["verify", str(path)])
    assert result.exit_code == 1


def test_cli_verify_unreadable(tmp_path):
    result = runner.invoke(cli_app, ["verify", str(tmp_path / "nope.rsc")])
    assert result.exit_code == 2


def test_cli_restore_dry_run_does_not_apply(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    path = tmp_path / "r1.rsc"
    path.write_text("/interface\n", encoding="utf-8")

    with patch("ros_manager.cli.restore.apply_restore") as mock_apply:
        result = runner.invoke(
            cli_app,
            ["restore", "--config", str(cfg_path), "--router", "r1", "--file", str(path)],
        )
    assert result.exit_code == 0
    assert "Restore plan for r1" in result.output
    mock_apply.assert_not_called()


def test_cli_restore_apply(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    path = tmp_path / "r1.rsc"
    path.write_text("/interface\n", encoding="utf-8")

    with patch("ros_manager.cli.restore.apply_restore", return_value="rosm-restore-x.rsc") as mock_apply:
        result = runner.invoke(
            cli_app,
            [
                "restore",
                "--config", str(cfg_path),
                "--router", "r1",
                "--file", str(path),
                "--apply",
            ],
        )
    assert result.exit_code == 0
    assert "uploaded" in result.output
    mock_apply.assert_called_once()
