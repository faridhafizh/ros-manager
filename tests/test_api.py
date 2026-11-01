"""FastAPI endpoint tests."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from ros_manager.api import create_app
from ros_manager.service import BackupResult, RouterResult
from ros_manager.models import RouterHealth


def test_api_post_backups_partial(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    cfg_path = write_yaml(good_yaml)
    app = create_app(cfg_path)
    client = TestClient(app)
    with patch("ros_manager.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(
                name="r1",
                host="10.0.0.1",
                backup=BackupResult(name="r1", host="10.0.0.1", status="ok", path="/backups/r1.rsc"),
            ),
            RouterResult(
                name="r2",
                host="10.0.0.2",
                backup=BackupResult(name="r2", host="10.0.0.2", status="error", error="ssh"),
            ),
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


def test_api_dashboard_lists_routers(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    client = TestClient(create_app(write_yaml(good_yaml)))
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "r1" in resp.text and "r2" in resp.text
    assert "api/status" in resp.text


def test_api_status_runs_checks_only(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    client = TestClient(create_app(write_yaml(good_yaml)))
    with patch("ros_manager.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(
                name="r1",
                host="10.0.0.1",
                health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
            )
        ]
        resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["routers"][0]["status"] == "ok"
    assert "backup" not in body["routers"][0]
    _, kwargs = mock_run.call_args
    assert kwargs["do_check"] is True
    assert kwargs["do_backup"] is False


def test_api_post_backups_new_endpoint(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    client = TestClient(create_app(write_yaml(minimal_yaml)))
    with patch("ros_manager.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(
                name="r1",
                host="10.0.0.1",
                backup=BackupResult(name="r1", host="10.0.0.1", status="ok", path="/b/r1.rsc"),
            )
        ]
        resp = client.post("/api/backups")
    assert resp.status_code == 200
    assert resp.json()["routers"][0]["backup"]["status"] == "ok"
    _, kwargs = mock_run.call_args
    assert kwargs["do_check"] is False
    assert kwargs["do_backup"] is True


def test_api_post_single_backup_scopes_config(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    client = TestClient(create_app(write_yaml(good_yaml)))
    with patch("ros_manager.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(
                name="r2",
                host="10.0.0.2",
                backup=BackupResult(name="r2", host="10.0.0.2", status="ok"),
            )
        ]
        resp = client.post("/api/backups/r2")
    assert resp.status_code == 200
    scoped = mock_run.call_args.args[0]
    assert [router.name for router in scoped.routers] == ["r2"]


def test_api_post_single_backup_unknown_router(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    client = TestClient(create_app(write_yaml(minimal_yaml)))
    resp = client.post("/api/backups/nope")
    assert resp.status_code == 404
    assert "unknown router" in resp.json()["detail"]


def test_api_config_invalid_dashboard_and_status(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("routers: [\n", encoding="utf-8")
    client = TestClient(create_app(bad))

    page = client.get("/")
    assert page.status_code == 500
    assert "text/html" in page.headers["content-type"]
    assert "config error" in page.text

    status = client.get("/api/status")
    assert status.status_code == 500
    assert "config error" in status.json()["detail"]

    single = client.post("/api/backups/r1")
    assert single.status_code == 500


def test_api_status_is_cached_briefly(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    client = TestClient(create_app(write_yaml(minimal_yaml)))
    with patch("ros_manager.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(
                name="r1",
                host="10.0.0.1",
                health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
            )
        ]
        first = client.get("/api/status")
        second = client.get("/api/status")
    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_run.call_count == 1


def test_api_history_records_status_points(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    client = TestClient(create_app(write_yaml(minimal_yaml)))
    with patch("ros_manager.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(
                name="r1",
                host="10.0.0.1",
                health=RouterHealth(
                    name="r1",
                    host="10.0.0.1",
                    status="ok",
                    cpu_load_percent=12.0,
                    memory_free_bytes=100,
                    memory_total_bytes=200,
                ),
            )
        ]
        client.get("/api/status")

    resp = client.get("/api/history?hours=24")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hours"] == 24
    points = body["series"]["r1"]
    assert len(points) == 1
    assert points[0]["cpu"] == 12.0
    assert points[0]["mem_free"] == 100


def test_api_history_clamps_hours(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    client = TestClient(create_app(write_yaml(minimal_yaml)))
    resp = client.get("/api/history?hours=999999")
    assert resp.status_code == 200
    assert resp.json()["hours"] == 24 * 30

