"""History listing and diff tests."""

from __future__ import annotations

from typer.testing import CliRunner

from ros_manager.cli import app as cli_app
from ros_manager.storage import latest_backup, list_backups

runner = CliRunner()


def _cfg(write_yaml, minimal_yaml, tmp_path):
    content = minimal_yaml + f"\nbackup_dir: {tmp_path / 'backups'}\n"
    return write_yaml(content)


def _seed(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "r1_20260101T000000.000000Z.rsc").write_text("/interface\n", encoding="utf-8")
    (backups / "r1_20260102T000000.000000Z.rsc").write_text("/interface\n", encoding="utf-8")
    (backups / "r2_20260101T000000.000000Z.rsc").write_text("/ip\n", encoding="utf-8")
    return backups


def test_list_backups_sorted_and_latest(tmp_path):
    _seed(tmp_path)
    files = list_backups(tmp_path / "backups", "r1")
    assert [p.name for p in files] == [
        "r1_20260101T000000.000000Z.rsc",
        "r1_20260102T000000.000000Z.rsc",
    ]
    assert latest_backup(tmp_path / "backups", "r1") == files[-1]
    assert latest_backup(tmp_path / "backups", "nope") is None


def test_cli_history_lists_backups(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _cfg(write_yaml, minimal_yaml, tmp_path)
    _seed(tmp_path)
    result = runner.invoke(
        cli_app, ["history", "--config", str(cfg_path), "--router", "r1"]
    )
    assert result.exit_code == 0
    assert "r1_20260102T000000.000000Z.rsc" in result.output
    assert "(2)" in result.output


def test_cli_history_unknown_router(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _cfg(write_yaml, minimal_yaml, tmp_path)
    result = runner.invoke(
        cli_app, ["history", "--config", str(cfg_path), "--router", "nope"]
    )
    assert result.exit_code == 2


def test_cli_history_no_backups(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _cfg(write_yaml, minimal_yaml, tmp_path)
    result = runner.invoke(
        cli_app, ["history", "--config", str(cfg_path), "--router", "r1"]
    )
    assert result.exit_code == 1


def test_cli_history_diff_identical(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _cfg(write_yaml, minimal_yaml, tmp_path)
    _seed(tmp_path)
    result = runner.invoke(
        cli_app, ["history", "--config", str(cfg_path), "--router", "r1", "--diff"]
    )
    assert result.exit_code == 0
    assert result.output == ""


def test_cli_history_diff_different(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _cfg(write_yaml, minimal_yaml, tmp_path)
    _seed(tmp_path)
    (tmp_path / "backups" / "r1_20260102T000000.000000Z.rsc").write_text(
        "/interface\n/ip address\n", encoding="utf-8"
    )
    result = runner.invoke(
        cli_app, ["history", "--config", str(cfg_path), "--router", "r1", "--diff"]
    )
    assert result.exit_code == 1
    assert "+++" in result.output


def test_cli_history_diff_needs_two(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _cfg(write_yaml, minimal_yaml, tmp_path)
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "r1_20260101T000000.000000Z.rsc").write_text("/interface\n", encoding="utf-8")
    result = runner.invoke(
        cli_app, ["history", "--config", str(cfg_path), "--router", "r1", "--diff"]
    )
    assert result.exit_code == 2
