"""RouterClient tests: health via API, config export via SSH."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ros_manager.router import RouterError


def test_get_health_ok(make_router, fake_api, monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    api = fake_api([
        [{"temperature": "52"}],  # /system/health/print
        [{"cpu-load": "35", "total-memory": "1024", "free-memory": "512"}],  # resource
        [
            {"name": "ether1", "type": "ether", "running": "true", "disabled": "false"},
            {"name": "sfp1", "type": "sfp", "running": "false", "disabled": "true"},
        ],  # /interface/print
    ])
    with patch("ros_manager.router.librouteros.connect", return_value=api):
        health = make_router().get_health()
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


def test_get_health_temperature_null_when_missing(make_router, fake_api, monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    api = fake_api([
        [],  # no temperature rows
        [{"cpu-load": "10", "total-memory": "100", "free-memory": "90"}],
        [],
    ])
    with patch("ros_manager.router.librouteros.connect", return_value=api):
        health = make_router().get_health()
    assert health.status == "ok"
    assert health.temperature_c is None


def test_get_health_api_error(make_router, monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    from librouteros.exceptions import LibRouterosError

    with patch(
        "ros_manager.router.librouteros.connect",
        side_effect=LibRouterosError("boom"),
    ):
        with pytest.raises(RouterError, match="API error"):
            make_router().get_health()


def test_export_config_success(make_router, monkeypatch):
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
                    out = make_router().export_config()
    assert out == "/system identity\n"


def test_export_config_ssh_failure(make_router, monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    import paramiko

    with patch.object(
        paramiko.SSHClient, "connect", side_effect=paramiko.SSHException("no route")
    ):
        with pytest.raises(RouterError, match="SSH error"):
            make_router().export_config()
