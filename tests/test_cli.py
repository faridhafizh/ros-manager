"""CLI command tests."""

from __future__ import annotations

import csv
import io
import json
from unittest.mock import patch

from typer.testing import CliRunner

from ros_manager.cli import app as cli_app
from ros_manager.models import RouterHealth
from ros_manager.service import BackupResult, RouterResult

runner = CliRunner()


def _run_cli(args, env=None):
    return runner.invoke(cli_app, args, env=env)


def test_cli_help_lists_commands():
    result = _run_cli(["--help"])
    assert result.exit_code == 0
    for command in ("check", "backup", "doctor", "run", "diff", "verify", "restore", "history", "schedule", "serve"):
        assert command in result.output


def test_cli_check_json(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    cfg_path = write_yaml(good_yaml)
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(name="r1", host="10.0.0.1", status="ok", temperature_c=None),
        ),
        RouterResult(
            name="r2",
            host="10.0.0.2",
            health=RouterHealth(name="r2", host="10.0.0.2", status="error", error="conn"),
        ),
    ]
    with patch("ros_manager.cli.check.run_inventory", return_value=results):
        result = _run_cli(["check", "--config", str(cfg_path), "--format", "json"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["routers"][0]["status"] == "ok"
    assert payload["routers"][1]["status"] == "error"
    assert payload["routers"][1]["temperature_c"] is None


def test_cli_check_csv_columns(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(name="r1", host="10.0.0.1", status="ok", temperature_c=None),
        ),
    ]
    with patch("ros_manager.cli.check.run_inventory", return_value=results):
        result = _run_cli(["check", "--config", str(cfg_path), "--format", "csv"])
    assert result.exit_code == 0
    reader = csv.DictReader(io.StringIO(result.output))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["name"] == "r1"
    assert rows[0]["temperature_c"] == ""
    assert set(reader.fieldnames) == {
        "name", "host", "status", "temperature_c", "cpu_load_percent",
        "memory_total_bytes", "memory_free_bytes", "interfaces_up", "interfaces_total", "error",
    }


def test_cli_check_text_output(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(
                name="r1", host="10.0.0.1", status="ok",
                temperature_c=50.0, cpu_load_percent=10.0,
            ),
        ),
    ]
    with patch("ros_manager.cli.check.run_inventory", return_value=results):
        result = _run_cli(["check", "--config", str(cfg_path), "--format", "text"])
    assert result.exit_code == 0
    assert "r1" in result.output
    assert "50.0" in result.output


def test_cli_check_html_report(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterResult(
            name="<b>r1</b>",
            host="10.0.0.1",
            health=RouterHealth(
                name="<b>r1</b>", host="10.0.0.1", status="ok", temperature_c=42.0
            ),
        ),
    ]
    with patch("ros_manager.cli.check.run_inventory", return_value=results):
        result = _run_cli(["check", "--config", str(cfg_path), "--format", "html"])
    assert result.exit_code == 0
    assert "<!doctype html>" in result.output
    assert "&lt;b&gt;r1&lt;/b&gt;" in result.output
    assert "<b>r1</b>" not in result.output


def test_cli_run_html_report_has_backup_columns(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
            backup=BackupResult(name="r1", host="10.0.0.1", status="ok", path="/b/r1.rsc"),
        ),
    ]
    with patch("ros_manager.cli.run.run_inventory", return_value=results):
        result = _run_cli(["run", "--config", str(cfg_path), "--format", "html"])
    assert result.exit_code == 0
    assert "Backup path" in result.output
    assert "/b/r1.rsc" in result.output


def test_cli_check_html_writes_output_file(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    out = tmp_path / "report.html"
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
        ),
    ]
    with patch("ros_manager.cli.check.run_inventory", return_value=results):
        result = _run_cli(
            ["check", "--config", str(cfg_path), "--format", "html", "--output", str(out)]
        )
    assert result.exit_code == 0
    assert "<!doctype html>" in out.read_text(encoding="utf-8")


def test_cli_invalid_format_exits_2(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    result = _run_cli(["check", "--config", str(cfg_path), "--format", "xml"])
    assert result.exit_code == 2
    assert "invalid format" in result.output


def test_cli_backup_writes_file(write_yaml, minimal_yaml, tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    fake_path = tmp_path / "backups" / "r1_20260101T000000.000000Z.rsc"
    fake_backup = BackupResult(name="r1", host="10.0.0.1", status="ok", path=str(fake_path))
    with patch(
        "ros_manager.cli.backup.run_inventory",
        return_value=[RouterResult(name="r1", host="10.0.0.1", backup=fake_backup)],
    ):
        result = _run_cli(["backup", "--config", str(cfg_path)])
    assert result.exit_code == 0
    assert "r1" in result.output


def test_cli_diff_same(tmp_path):
    a = tmp_path / "a.rsc"
    b = tmp_path / "b.rsc"
    a.write_text("x\n", encoding="utf-8")
    b.write_text("x\n", encoding="utf-8")
    result = _run_cli(["diff", str(a), str(b)])
    assert result.exit_code == 0
    assert result.output == ""


def test_cli_diff_different(tmp_path):
    a = tmp_path / "a.rsc"
    b = tmp_path / "b.rsc"
    a.write_text("x\n", encoding="utf-8")
    b.write_text("y\n", encoding="utf-8")
    result = _run_cli(["diff", str(a), str(b)])
    assert result.exit_code == 1
    assert "---" in result.output or "+++" in result.output


def test_cli_diff_unreadable(tmp_path):
    result = _run_cli(["diff", str(tmp_path / "nope.rsc"), str(tmp_path / "nope2.rsc")])
    assert result.exit_code == 2


def test_cli_missing_config(tmp_path):
    result = _run_cli(["check", "--config", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 2


def test_cli_check_router_filter(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    cfg_path = write_yaml(good_yaml)
    with patch("ros_manager.cli.check.run_inventory", return_value=[]) as mock_run:
        result = _run_cli(["check", "--config", str(cfg_path), "--router", "r2"])
    assert result.exit_code == 0
    called_cfg = mock_run.call_args.args[0]
    assert [r.name for r in called_cfg.routers] == ["r2"]


def test_cli_check_group_filter(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    content = """
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
    groups: [core]
  - name: r2
    host: 10.0.0.2
    username: admin
    password_env: R2_PASS
    groups: [edge]
"""
    cfg_path = write_yaml(content)
    with patch("ros_manager.cli.check.run_inventory", return_value=[]) as mock_run:
        result = _run_cli(["check", "--config", str(cfg_path), "--group", "edge"])
    assert result.exit_code == 0
    called_cfg = mock_run.call_args.args[0]
    assert [r.name for r in called_cfg.routers] == ["r2"]


def test_cli_check_unknown_router(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    cfg_path = write_yaml(good_yaml)
    result = _run_cli(["check", "--config", str(cfg_path), "--router", "nope"])
    assert result.exit_code == 2
    assert "unknown router" in result.output


def test_cli_run_notify_uses_flap_notifications(write_yaml, minimal_yaml, monkeypatch):
    from ros_manager.notify import NotifyOutcome

    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
        ),
    ]
    with patch("ros_manager.cli.run.run_inventory", return_value=results):
        with patch(
            "ros_manager.cli.run.send_notifications",
            return_value=NotifyOutcome(sent=True, changed=["r1"]),
        ) as mock_notify:
            result = _run_cli(["run", "--config", str(cfg_path), "--notify"])
    assert result.exit_code == 0
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["notify_all"] is False


def test_cli_run_notify_skipped_message(write_yaml, minimal_yaml, monkeypatch):
    from ros_manager.notify import NotifyOutcome

    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
        ),
    ]
    with patch("ros_manager.cli.run.run_inventory", return_value=results):
        with patch(
            "ros_manager.cli.run.send_notifications",
            return_value=NotifyOutcome(sent=False, changed=[], skipped_reason="no status changes"),
        ):
            result = _run_cli(["run", "--config", str(cfg_path), "--notify"])
    assert result.exit_code == 0
    assert "no status changes" in result.output
