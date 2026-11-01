"""Config loading and validation tests."""

from __future__ import annotations

import pytest

from ros_manager.config import ConfigError, load_config


def test_load_config_valid(write_yaml, good_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "secret1")
    monkeypatch.setenv("R2_PASS", "secret2")
    cfg = load_config(write_yaml(good_yaml))
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


def test_load_config_defaults_backup_dir(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    cfg = load_config(write_yaml(minimal_yaml))
    assert cfg.backup_dir == "backups"


def test_load_config_empty_routers(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    with pytest.raises(ConfigError, match="non-empty"):
        load_config(write_yaml("routers: []\n"))


def test_load_config_missing_routers(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    with pytest.raises(ConfigError, match="required"):
        load_config(write_yaml("backup_dir: backups\n"))


def test_load_config_env_password_missing(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.delenv("R1_PASS", raising=False)
    with pytest.raises(ConfigError, match="unset or empty"):
        load_config(write_yaml(minimal_yaml))


def test_load_config_env_password_empty(write_yaml, minimal_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "   ")
    with pytest.raises(ConfigError, match="unset or empty"):
        load_config(write_yaml(minimal_yaml))


def test_load_config_invalid_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    path = tmp_path / "bad.yaml"
    path.write_text("routers: [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(path)


def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_load_config_router_field_errors(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    bad = """
routers:
  - host: 10.0.0.1
    username: admin
    password_env: R1_PASS
"""
    with pytest.raises(ConfigError, match="name"):
        load_config(write_yaml(bad))


def test_load_config_telegram_invalid_pair(write_yaml, monkeypatch):
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
        load_config(write_yaml(bad))


def test_load_config_groups_and_retention(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
retention:
  keep_last: 14
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
    groups: [core, edge]
    retention:
      keep_last: 30
  - name: r2
    host: 10.0.0.2
    username: admin
    password_env: R1_PASS
"""
    cfg = load_config(write_yaml(content))
    assert cfg.retention_keep_last == 14
    r1, r2 = cfg.routers
    assert r1.groups == ("core", "edge")
    assert r1.retention_keep_last == 30
    assert r2.groups == ()
    assert r2.retention_keep_last is None


def test_load_config_retention_must_be_positive(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
retention:
  keep_last: 0
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
"""
    with pytest.raises(ConfigError, match="must be >= 1"):
        load_config(write_yaml(content))


def test_load_config_groups_must_be_list(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
    groups: core
"""
    with pytest.raises(ConfigError, match="expected a list"):
        load_config(write_yaml(content))


def test_load_config_duplicate_router_names(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
  - name: r1
    host: 10.0.0.2
    username: admin
    password_env: R1_PASS
"""
    with pytest.raises(ConfigError, match="duplicate router name"):
        load_config(write_yaml(content))


def test_load_config_notifications(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
state_file: /tmp/rosm-state.json
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
notifications:
  telegram:
    token_env: BOT_TOKEN
    chat_id: "42"
  webhook:
    url_env: HOOK_URL
    style: discord
"""
    cfg = load_config(write_yaml(content))
    assert cfg.state_file == "/tmp/rosm-state.json"
    assert cfg.notifications is not None
    assert cfg.notifications.telegram.token_env == "BOT_TOKEN"
    assert cfg.notifications.webhook.url_env == "HOOK_URL"
    assert cfg.notifications.webhook.style == "discord"


def test_load_config_webhook_invalid_style(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
notifications:
  webhook:
    url_env: HOOK_URL
    style: carrier-pigeon
"""
    with pytest.raises(ConfigError, match="must be one of"):
        load_config(write_yaml(content))


def test_load_config_webhook_requires_url_env(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
notifications:
  webhook:
    style: generic
"""
    with pytest.raises(ConfigError, match="url_env"):
        load_config(write_yaml(content))


def test_load_config_empty_state_file(write_yaml, monkeypatch):
    monkeypatch.setenv("R1_PASS", "pw")
    content = """
state_file: "  "
routers:
  - name: r1
    host: 10.0.0.1
    username: admin
    password_env: R1_PASS
"""
    with pytest.raises(ConfigError, match="state_file"):
        load_config(write_yaml(content))


# -- include: multi-file inventories -------------------------------------


def _router_yaml(name, host, env):
    return f"""
routers:
  - name: {name}
    host: {host}
    username: admin
    password_env: {env}
"""


def test_include_single_file(write_yaml, monkeypatch, tmp_path):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    (tmp_path / "routers.yaml").write_text(
        _router_yaml("r2", "10.0.0.2", "R2_PASS"), encoding="utf-8"
    )
    cfg = load_config(
        write_yaml(
            _router_yaml("r1", "10.0.0.1", "R1_PASS")
            + "\ninclude: routers.yaml\n"
        )
    )
    assert [r.name for r in cfg.routers] == ["r1", "r2"]


def test_include_glob_and_relative_subdir(write_yaml, monkeypatch, tmp_path):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    monkeypatch.setenv("R3_PASS", "pw")
    sub = tmp_path / "routers"
    sub.mkdir()
    (sub / "a.yaml").write_text(
        _router_yaml("r1", "10.0.0.1", "R1_PASS"), encoding="utf-8"
    )
    (sub / "b.yaml").write_text(
        _router_yaml("r2", "10.0.0.2", "R2_PASS"), encoding="utf-8"
    )
    cfg = load_config(write_yaml("include: routers/*.yaml\n"))
    assert [r.name for r in cfg.routers] == ["r1", "r2"]


def test_include_recursive(write_yaml, monkeypatch, tmp_path):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    monkeypatch.setenv("R3_PASS", "pw")
    (tmp_path / "level2.yaml").write_text(
        _router_yaml("r3", "10.0.0.3", "R3_PASS"), encoding="utf-8"
    )
    (tmp_path / "level1.yaml").write_text(
        _router_yaml("r2", "10.0.0.2", "R2_PASS")
        + "\ninclude: level2.yaml\n",
        encoding="utf-8",
    )
    cfg = load_config(
        write_yaml(
            _router_yaml("r1", "10.0.0.1", "R1_PASS")
            + "\ninclude: level1.yaml\n"
        )
    )
    assert [r.name for r in cfg.routers] == ["r1", "r2", "r3"]


def test_include_cycle_detected(write_yaml, monkeypatch, tmp_path):
    monkeypatch.setenv("R1_PASS", "pw")
    monkeypatch.setenv("R2_PASS", "pw")
    (tmp_path / "a.yaml").write_text(
        _router_yaml("r1", "10.0.0.1", "R1_PASS") + "\ninclude: b.yaml\n",
        encoding="utf-8",
    )
    (tmp_path / "b.yaml").write_text(
        _router_yaml("r2", "10.0.0.2", "R2_PASS") + "\ninclude: a.yaml\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="include cycle"):
        load_config(write_yaml("include: a.yaml\n"))


def test_include_missing_file(write_yaml):
    with pytest.raises(ConfigError, match="include not found"):
        load_config(write_yaml("include: nope.yaml\n"))


def test_include_duplicate_router_name(write_yaml, monkeypatch, tmp_path):
    monkeypatch.setenv("R1_PASS", "pw")
    (tmp_path / "other.yaml").write_text(
        _router_yaml("r1", "10.0.0.9", "R1_PASS"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="duplicate router name"):
        load_config(
            write_yaml(
                _router_yaml("r1", "10.0.0.1", "R1_PASS")
                + "\ninclude: other.yaml\n"
            )
        )


def test_include_requires_string_or_list(write_yaml):
    with pytest.raises(ConfigError, match="include"):
        load_config(write_yaml("include: {a: 1}\n"))


def test_include_empty_list_without_routers(write_yaml):
    with pytest.raises(ConfigError, match="no routers defined"):
        load_config(write_yaml("include: []\n"))


def test_include_invalid_included_yaml(write_yaml, tmp_path):
    (tmp_path / "bad.yaml").write_text("routers: [\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(write_yaml("include: bad.yaml\n"))
