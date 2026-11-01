"""Shared test fixtures. No real routers, network, or tokens are used."""

from __future__ import annotations

from pathlib import Path

import pytest

from ros_manager.models import RouterConfig
from ros_manager.router import RouterClient

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


@pytest.fixture
def good_yaml() -> str:
    return GOOD_YAML


@pytest.fixture
def minimal_yaml() -> str:
    return MINIMAL_YAML


@pytest.fixture
def write_yaml(tmp_path):
    """Write a YAML file into tmp_path and return its path.

    A per-test ``metrics_db`` path is appended so the dashboard never writes
    its SQLite history into the repository working directory.
    """

    def _write(content: str, name: str = "config.yaml") -> Path:
        path = tmp_path / name
        text = content
        if "metrics_db:" not in text:
            db_path = (tmp_path / "metrics.db").as_posix()
            text = text.rstrip() + f"\nmetrics_db: {db_path}\n"
        path.write_text(text, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def make_router():
    """Build a RouterClient for tests without touching the network."""

    def _make(host: str = "10.0.0.1", name: str = "r1") -> RouterClient:
        return RouterClient(
            RouterConfig(
                name=name,
                host=host,
                username="admin",
                password_env="R_PASS",
            )
        )

    return _make


class FakeApi:
    """Fake librouteros Api that returns canned rows per ``__call__``."""

    def __init__(self, results):
        self._results = iter(results)

    def __call__(self, *args, **kwargs):
        return iter(next(self._results))

    def close(self):
        pass


@pytest.fixture
def fake_api():
    return FakeApi
