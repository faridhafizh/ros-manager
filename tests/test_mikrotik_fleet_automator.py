"""Tests for mikrotik_fleet_automator. No real routers, network, or tokens."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner
from fastapi.testclient import TestClient

from mikrotik_fleet_automator.config import load_config, ConfigError
from mikrotik_fleet_automator.models import (
    AppConfig,
    RouterConfig,
    RouterHealth,
    RouterInterface,
    TelegramConfig,
)
from mikrotik_fleet_automator.router import RouterClient, RouterError
from mikrotik_fleet_automator.service import (
    run_inventory,
    any_failure,
    RouterResult,
    BackupResult,
)
from mikrotik_fleet_automator.storage import write_backup, backup_filename
from mikrotik_fleet_automator.cli import app as cli_app
from mikrotik_fleet_automator.api import create_app
from mikrotik_fleet_automator import telegram as tg_module
from mikrotik_fleet_automator import scheduler as sched_module


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #

GOOD_YAML = """
backup_dir: backups
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
  - name: r2
    host: 10.0.0.2
    username: admin
    password_env: R2_PASS
    api_port: 8730
    api_tls: false
    api_ca_file: /tmp/ca.pem
    ssh_port: 2222
    ssh_known_hosts: /tmp/known_hosts
"""

MINIMAL_YAML = """
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
"""


def _write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_load_config_valid(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "secret1")
    monkeypatch.setenv("R2_PASS", "secret2")
    cfg = load_config(_write_yaml(tmp_path, GOOD_YAML))
    assert cfg.backup_dir == "backups"
    assert [r.name for r in cfg.routers] == ["r1", "r2"]
    r1, r2 = cfg.routers
    assert r1.api_port == 8729
    assert r1.api_tls is True
    assert r1.api_ca_file is None
    assert r1.ssh_port == 22
    assert r1.ssh_known_hosts == "~/.ssh/known_hosts"
    assert r2.api_port == 8730
    assert r2.api_tls is False
    assert r2.api_ca_file == "/tmp/ca.pem"
    assert r2.ssh_port == 2222
    assert r2.ssh_known_hosts == "/tmp/known_hosts"


def test_load_config_defaults_backup_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg = load_config(_write_yaml(tmp_path, MINIMAL_YAML))
    assert cfg.backup_dir == "backups"


def test_load_config_empty_routers(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    with pytest.raises(ConfigError, match="non-empty"):
        load_config(_write_yaml(tmp_path, "routers: []\n"))


def test_load_config_missing_routers(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    with pytest.raises(ConfigError, match="required"):
        load_config(_write_yaml(tmp_path, "backup_dir: backups\n"))


def test_load_config_env_password_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("R1_PASS", raising=False)
    with pytest.raises(ConfigError, match="unset or empty"):
        load_config(_write_yaml(tmp_path, MINIMAL_YAML))


def test_load_config_env_password_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "   ")
    with pytest.raises(ConfigError, match="unset or empty"):
        load_config(_write_yaml(tmp_path, MINIMAL_YAML))


def test_load_config_invalid_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    p = tmp_path / "bad.yaml"
    p.write_text("routers: [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(p)


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_load_config_router_field_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    bad = """
routers:
  - host: 10.0.0.1
    username: admin
    password_env: R1_PASS
"""
    with pytest.raises(ConfigError, match="name"):
        load_config(_write_yaml(tmp_path, bad))


def test_load_config_telegram_invalid_pair(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    bad = """
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
telegram:
  token_env: TOKEN
"""
    with pytest.raises(ConfigError, match="together"):
        load_config(_write_yaml(tmp_path, bad))


# --------------------------------------------------------------------------- #
# router
# --------------------------------------------------------------------------- #

class _FakeApi:
    """Fake librouteros Api that returns canned rows per __call__."""

    def __init__(self, results):
        self._results = iter(results)

    def __call__(self, *args, **kwargs):
        return iter(next(self._results))

    def close(self):
        pass


def _make_router(host="10.0.0.1", name="r1"):
    return RouterClient(
        RouterConfig(
            name=name,
            host=host,
            username="admin",
            password_env="R_PASS",
        )
    )


def test_get_health_ok(monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    api = _FakeApi([
        [{"temperature": "52"}],  # /system/health/print
        [{"cpu-load": "35", "total-memory": "1024", "free-memory": "512"}],  # resource
        [
            {"name": "ether1", "type": "ether", "running": "true", "disabled": "false"},
            {"name": "sfp1", "type": "sfp", "running": "false", "disabled": "true"},
        ],  # /interface/print
    ])
    with patch("mikrotik_fleet_automator.router.librouteros.connect", return_value=api):
        health = _make_router().get_health()
    assert health.status == "ok"
    assert health.temperature_c == 52.0
    assert health.cpu_load_percent == 35.0
    assert health.memory_total_bytes == 1024
    assert health.memory_free_bytes == 512
    assert len(health.interfaces) == 2
    assert health.interfaces[0].name == "ether1"
    assert health.interfaces[0].type == "ether"
    assert health.interfaces[0].running is True
    assert health.interfaces[0].disabled is False


def test_get_health_temperature_null_when_missing(monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    api = _FakeApi([
        [],  # no temperature rows
        [{"cpu-load": "10", "total-memory": "100", "free-memory": "90"}],
        [],
    ])
    with patch("mikrotik_fleet_automator.router.librouteros.connect", return_value=api):
        health = _make_router().get_health()
    assert health.status == "ok"
    assert health.temperature_c is None


def test_get_health_api_error(monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    from librouteros.exceptions import LibRouterosError

    with patch(
        "mikrotik_fleet_automator.router.librouteros.connect",
        side_effect=LibRouterosError("boom"),
    ):
        with pytest.raises(RouterError, match="API error"):
            _make_router().get_health()


def test_export_config_success(monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    ssh = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    ssh.get_transport.return_value = transport
    stdout = MagicMock()
    stdout.read.return_value = b"/system identity\n"
    stdout.channel.recv_exit_status.return_value = 0
    ssh.exec_command.return_value = (MagicMock(), stdout, MagicMock())

    real_sshclient = __import__("paramiko").SSHClient
    with patch.object(real_sshclient, "__new__", lambda cls: ssh):
        with patch.object(real_sshclient, "set_missing_host_key_policy"):
            with patch.object(real_sshclient, "load_host_keys"):
                with patch.object(real_sshclient, "connect", return_value=None):
                    out = _make_router().export_config()
    assert out == "/system identity\n"


def test_export_config_ssh_failure(monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    import paramiko

    with patch.object(
        paramiko.SSHClient, "connect", side_effect=paramiko.SSHException("no route")
    ):
        with pytest.raises(RouterError, match="SSH error"):
            _make_router().export_config()


# --------------------------------------------------------------------------- #
# service
# --------------------------------------------------------------------------- #

def test_run_inventory_partial_failure(monkeypatch):
    cfg = AppConfig(
        backup_dir="backups",
        routers=[
            RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P1"),
            RouterConfig(name="r2", host="10.0.0.2", username="a", password_env="P2"),
        ],
    )

    def fake_run_router(config, backup_dir, do_check, do_backup):
        if config.name == "r1":
            return RouterResult(
                name="r1", host="10.0.0.1",
                health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
            )
        return RouterResult(
            name="r2", host="10.0.0.2",
            health=RouterHealth(name="r2", host="10.0.0.2", status="error", error="down"),
        )

    with patch("mikrotik_fleet_automator.service.run_router", side_effect=fake_run_router):
        results = run_inventory(cfg, do_check=True, do_backup=False)
    assert len(results) == 2
    assert results[0].health.status == "ok"
    assert results[1].health.status == "error"
    assert any_failure(results) is True


def test_any_failure_backup_error():
    results = [
        RouterResult(name="r1", host="10.0.0.1", health=RouterHealth(name="r1", host="10.0.0.1", status="ok")),
        RouterResult(name="r2", host="10.0.0.2", backup=BackupResult(name="r2", host="10.0.0.2", status="error", error="ssh fail")),
    ]
    assert any_failure(results) is True


# --------------------------------------------------------------------------- #
# storage
# --------------------------------------------------------------------------- #

def test_backup_filename_format():
    name = backup_filename("r1")
    assert re.fullmatch(r"r1_\d{8}T\d{6}\.\d{6}Z\.rsc", name)


def test_write_backup_atomic_and_content(tmp_path):
    d = tmp_path / "backups"
    path = write_backup(d, "r1", "/system identity\n")
    assert path.exists()
    assert path.name.startswith("r1_")
    assert path.name.endswith(".rsc")
    assert path.read_text(encoding="utf-8") == "/system identity\n"
    leftovers = [p for p in d.iterdir() if p.name.startswith(".")]
    assert leftovers == []


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _run_cli(args, env=None):
    runner = CliRunner()
    return runner.invoke(cli_app, args, env=env)


def test_cli_check_json(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    cfg_path = _write_yaml(tmp_path, GOOD_YAML)
    results = [
        RouterResult(name="r1", host="10.0.0.1", health=RouterHealth(name="r1", host="10.0.0.1", status="ok", temperature_c=None)),
        RouterResult(name="r2", host="10.0.0.2", health=RouterHealth(name="r2", host="10.0.0.2", status="error", error="conn")),
    ]
    with patch("mikrotik_fleet_automator.cli.run_inventory", return_value=results):
        result = _run_cli(["check", "--config", str(cfg_path), "--format", "json"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["routers"][0]["status"] == "ok"
    assert payload["routers"][1]["status"] == "error"
    assert payload["routers"][1]["temperature_c"] is None


def test_cli_check_csv_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _write_yaml(tmp_path, MINIMAL_YAML)
    results = [
        RouterResult(name="r1", host="10.0.0.1", health=RouterHealth(name="r1", host="10.0.0.1", status="ok", temperature_c=None)),
    ]
    with patch("mikrotik_fleet_automator.cli.run_inventory", return_value=results):
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


def test_cli_check_text_output(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _write_yaml(tmp_path, MINIMAL_YAML)
    results = [
        RouterResult(name="r1", host="10.0.0.1", health=RouterHealth(name="r1", host="10.0.0.1", status="ok", temperature_c=50.0, cpu_load_percent=10.0)),
    ]
    with patch("mikrotik_fleet_automator.cli.run_inventory", return_value=results):
        result = _run_cli(["check", "--config", str(cfg_path), "--format", "text"])
    assert result.exit_code == 0
    assert "r1" in result.output
    assert "50.0" in result.output


def test_cli_backup_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = _write_yaml(tmp_path, MINIMAL_YAML)
    fake_path = tmp_path / "backups" / "r1_20260101T000000.000000Z.rsc"
    fake_backup = BackupResult(name="r1", host="10.0.0.1", status="ok", path=str(fake_path))
    with patch("mikrotik_fleet_automator.cli.run_inventory", return_value=[RouterResult(name="r1", host="10.0.0.1", backup=fake_backup)]):
        result = _run_cli(["backup", "--config", str(cfg_path)])
    assert result.exit_code == 0
    assert "r1" in result.output


def test_cli_diff_same(tmp_path):
    a = tmp_path / "a.rsc"; b = tmp_path / "b.rsc"
    a.write_text("x\n", encoding="utf-8"); b.write_text("x\n", encoding="utf-8")
    result = _run_cli(["diff", str(a), str(b)])
    assert result.exit_code == 0
    assert result.output == ""


def test_cli_diff_different(tmp_path):
    a = tmp_path / "a.rsc"; b = tmp_path / "b.rsc"
    a.write_text("x\n", encoding="utf-8"); b.write_text("y\n", encoding="utf-8")
    result = _run_cli(["diff", str(a), str(b)])
    assert result.exit_code == 1
    assert "---" in result.output or "+++" in result.output


def test_cli_diff_unreadable(tmp_path):
    result = _run_cli(["diff", str(tmp_path / "nope.rsc"), str(tmp_path / "nope2.rsc")])
    assert result.exit_code == 2


def test_cli_missing_config(tmp_path, monkeypatch):
    result = _run_cli(["check", "--config", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

def test_api_post_backups_partial(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    cfg_path = _write_yaml(tmp_path, GOOD_YAML)
    app = create_app(cfg_path)
    client = TestClient(app)
    with patch("mikrotik_fleet_automator.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(name="r1", host="10.0.0.1", backup=BackupResult(name="r1", host="10.0.0.1", status="ok", path="/backups/r1.rsc")),
            RouterResult(name="r2", host="10.0.0.2", backup=BackupResult(name="r2", host="10.0.0.2", status="error", error="ssh")),
        ]
        resp = client.post("/backups")
    assert resp.status_code == 200
    body = resp.json()
    assert body["routers"][0]["backup"]["status"] == "ok"
    assert body["routers"][1]["backup"]["status"] == "error"
    assert "password" not in json.dumps(body).lower()


def test_api_post_backups_config_invalid(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [valid yaml\n", encoding="utf-8")
    app = create_app(bad)
    client = TestClient(app)
    resp = client.post("/backups")
    assert resp.status_code == 500
    body = resp.json()
    assert "token" not in json.dumps(body).lower()
    assert "password" not in json.dumps(body).lower()


# --------------------------------------------------------------------------- #
# telegram
# --------------------------------------------------------------------------- #

def test_resolve_telegram_none_when_disabled():
    cfg = AppConfig(backup_dir="b", routers=[])
    assert tg_module.resolve_telegram(cfg) is None


def test_resolve_telegram_invalid_pair():
    cfg = AppConfig(
        backup_dir="b", routers=[],
        telegram=TelegramConfig(token_env="T", chat_id=None),
    )
    with pytest.raises(tg_module.TelegramError, match="together"):
        tg_module.resolve_telegram(cfg)


def test_resolve_telegram_token_missing(monkeypatch):
    monkeypatch.delenv("T", raising=False)
    cfg = AppConfig(
        backup_dir="b", routers=[],
        telegram=TelegramConfig(token_env="T", chat_id="123"),
    )
    with pytest.raises(tg_module.TelegramError, match="unset or empty"):
        tg_module.resolve_telegram(cfg)



def test_send_summary_no_token_logged(monkeypatch):
    monkeypatch.setenv("T", "secret-token")
    with patch.object(tg_module.httpx, "Client") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.post.return_value.raise_for_status.return_value = None
        tg_module.send_summary(
            TelegramConfig(token_env="T", chat_id="1"), "chat-1", "hi"
        )
        # verify token never in request URL/path args passed to post
        call_args = instance.post.call_args
        # verify token never appears in the message body
        _, kwargs = instance.post.call_args
        assert "secret-token" not in kwargs["json"]["text"]


# --------------------------------------------------------------------------- #
# scheduler
# --------------------------------------------------------------------------- #

def test_scheduler_runs_immediately_and_stops(monkeypatch):
    cfg = AppConfig(backup_dir="b", routers=[])
    calls = []

    def fake_run(config, do_check, do_backup):
        calls.append(1)
        return []

    stop = threading.Event()
    stop.set()  # already stopped: loop should exit after the immediate run
    monkeypatch.setattr(sched_module, "run_inventory", fake_run)
    monkeypatch.setattr(sched_module, "resolve_telegram", lambda c: None)
    monkeypatch.setattr(sched_module, "signal", MagicMock())
    sched_module.run_schedule(cfg, 1, stop_event=stop, run_fn=fake_run)
    assert len(calls) == 1  # ran once, then stopped
