"""Dashboard authentication tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from ros_manager.api import create_app
from ros_manager.auth import SessionStore
from ros_manager.models import RouterHealth
from ros_manager.service import RouterResult


def _client(write_yaml, minimal_yaml, monkeypatch, password=None) -> TestClient:
    monkeypatch.setenv("R1_PASS", "pw")
    if password is None:
        monkeypatch.delenv("ROSM_DASH_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("ROSM_DASH_PASSWORD", password)
    return TestClient(create_app(write_yaml(minimal_yaml)))


def test_dashboard_open_without_password(write_yaml, minimal_yaml, monkeypatch):
    client = _client(write_yaml, minimal_yaml, monkeypatch)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Log out" not in resp.text


def test_dashboard_requires_login_when_password_set(
    write_yaml, minimal_yaml, monkeypatch
):
    client = _client(write_yaml, minimal_yaml, monkeypatch, "team-secret")

    page = client.get("/", follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"] == "/login"

    login = client.get("/login")
    assert login.status_code == 200
    assert "team-secret" not in login.text

    api = client.get("/api/status")
    assert api.status_code == 401
    assert api.json()["detail"] == "unauthorized"


def test_login_with_wrong_password_is_rejected(
    write_yaml, minimal_yaml, monkeypatch
):
    client = _client(write_yaml, minimal_yaml, monkeypatch, "team-secret")
    resp = client.post(
        "/login", data={"password": "nope"}, follow_redirects=False
    )
    assert resp.status_code == 401
    assert "Incorrect password" in resp.text


def test_login_grants_dashboard_and_api_access(
    write_yaml, minimal_yaml, monkeypatch
):
    client = _client(write_yaml, minimal_yaml, monkeypatch, "team-secret")
    resp = client.post(
        "/login", data={"password": "team-secret"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert "rosm_session" in resp.cookies

    page = client.get("/")
    assert page.status_code == 200
    assert "Log out" in page.text

    with patch("ros_manager.api.run_inventory") as mock_run:
        mock_run.return_value = [
            RouterResult(
                name="r1",
                host="10.0.0.1",
                health=RouterHealth(name="r1", host="10.0.0.1", status="ok"),
            )
        ]
        status = client.get("/api/status")
    assert status.status_code == 200


def test_logout_revokes_session(write_yaml, minimal_yaml, monkeypatch):
    client = _client(write_yaml, minimal_yaml, monkeypatch, "team-secret")
    client.post("/login", data={"password": "team-secret"})
    client.post("/logout", follow_redirects=False)

    assert client.get("/api/status").status_code == 401


def test_sessions_expire():
    store = SessionStore(ttl_seconds=0)
    token = store.create()
    assert store.is_valid(token) is False
    assert store.is_valid("bogus") is False
