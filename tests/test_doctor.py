"""Doctor diagnostics tests: router mapping, service isolation, CLI output."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ros_manager.cli import app as cli_app
from ros_manager.models import AppConfig, RouterConfig, RouterDoctor
from ros_manager.router import RouterError
from ros_manager.service import run_doctor_inventory

runner = CliRunner()


def test_get_doctor_maps_fields(make_router, fake_api, monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    api = fake_api([
        [{"name": "r1"}],  # /system/identity/print (latency probe)
        [{
            "version": "7.16.2",
            "uptime": "1w2d",
            "board-name": "RB5009UG+S+",
            "architecture-name": "arm64",
            "cpu-count": "4",
            "total-hdd-space": "134217728",
            "free-hdd-space": "67108864",
        }],  # /system/resource/print
        [
            {"name": "temperature", "value": "45"},
            {"name": "voltage", "value": "24.1"},
            {"name": "fan1-speed", "value": "1200"},
        ],  # /system/health/print (v6 name/value shape)
    ])
    with patch("ros_manager.router.librouteros.connect", return_value=api):
        doctor = make_router().get_doctor()

    assert doctor.status == "ok"
    assert doctor.version == "7.16.2"
    assert doctor.uptime == "1w2d"
    assert doctor.board_name == "RB5009UG+S+"
    assert doctor.architecture == "arm64"
    assert doctor.cpu_count == 4
    assert doctor.disk_total_bytes == 134217728
    assert doctor.disk_free_bytes == 67108864
    assert doctor.temperature_c == 45.0
    assert doctor.voltage == 24.1
    assert doctor.fan_speed == 1200.0
    assert doctor.latency_ms is not None
    assert doctor.latency_ms >= 0


def test_get_doctor_single_row_health_shape(make_router, fake_api, monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    api = fake_api([
        [],
        [{"version": "7.16.2"}],
        [{"temperature": "41", "voltage": "24.0"}],  # v7 single-row shape
    ])
    with patch("ros_manager.router.librouteros.connect", return_value=api):
        doctor = make_router().get_doctor()
    assert doctor.temperature_c == 41.0
    assert doctor.voltage == 24.0
    assert doctor.fan_speed is None


def test_get_doctor_api_error(make_router, monkeypatch):
    monkeypatch.setenv("R_PASS", "pw")
    from librouteros.exceptions import LibRouterosError

    with patch(
        "ros_manager.router.librouteros.connect",
        side_effect=LibRouterosError("boom"),
    ):
        with pytest.raises(RouterError, match="API error"):
            make_router().get_doctor()


def test_run_doctor_inventory_isolates_failure():
    cfg = AppConfig(
        backup_dir="b",
        routers=[
            RouterConfig(name="r1", host="10.0.0.1", username="a", password_env="P"),
            RouterConfig(name="r2", host="10.0.0.2", username="a", password_env="P"),
        ],
    )

    def fake_doctor(config):
        if config.name == "r1":
            return RouterDoctor(name="r1", host=config.host, status="ok", version="7.16.2")
        raise RouterError("unreachable")

    with patch("ros_manager.service.doctor_router", side_effect=fake_doctor):
        results = run_doctor_inventory(cfg)

    assert results[0].status == "ok"
    assert results[1].status == "error"
    assert results[1].error == "unreachable"


def test_cli_doctor_json(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterDoctor(
            name="r1",
            host="10.0.0.1",
            status="ok",
            version="7.16.2",
            board_name="RB5009",
            latency_ms=12.5,
        )
    ]
    with patch("ros_manager.cli.doctor.run_doctor_inventory", return_value=results):
        result = runner.invoke(
            cli_app, ["doctor", "--config", str(cfg_path), "--format", "json"]
        )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["routers"][0]["version"] == "7.16.2"
    assert payload["routers"][0]["latency_ms"] == 12.5


def test_cli_doctor_failure_exit_code(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg_path = write_yaml(minimal_yaml)
    results = [
        RouterDoctor(name="r1", host="10.0.0.1", status="error", error="down")
    ]
    with patch("ros_manager.cli.doctor.run_doctor_inventory", return_value=results):
        result = runner.invoke(cli_app, ["doctor", "--config", str(cfg_path)])
    assert result.exit_code == 1
    assert "down" in result.output
