"""YAML configuration loading and validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .models import (
    AppConfig,
    RouterConfig,
    TelegramConfig,
)


class ConfigError(Exception):
    """Raised when the inventory YAML is invalid or a secret is missing."""


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{context}: expected a mapping, got {type(value).__name__}")
    return value


def _require_str(value: Any, context: str, field: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(
            f"{context}.{field}: expected a string, got {type(value).__name__}"
        )
    return value


def _require_nonempty_str(value: Any, context: str, field: str) -> str:
    text = _require_str(value, context, field)
    if not text.strip():
        raise ConfigError(f"{context}.{field}: must not be empty")
    return text


def _optional_int(
    value: Any, context: str, field: str, default: int
) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(
            f"{context}.{field}: expected an integer, got {type(value).__name__}"
        )
    return value


def _optional_bool(
    value: Any, context: str, field: str, default: bool
) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConfigError(
            f"{context}.{field}: expected a boolean, got {type(value).__name__}"
        )
    return value


def _load_router(raw: Any, index: int) -> RouterConfig:
    context = f"routers[{index}]"
    router = _require_mapping(raw, context)

    name = _require_nonempty_str(
        router.get("name"), context, "name"
    )
    host = _require_nonempty_str(router.get("host"), context, "host")
    username = _require_nonempty_str(
        router.get("username"), context, "username"
    )
    password_env = _require_nonempty_str(
        router.get("password_env"), context, "password_env"
    )
    api_port = _optional_int(router.get("api_port"), context, "api_port", 8729)
    api_tls = _optional_bool(router.get("api_tls"), context, "api_tls", True)
    api_ca_file = router.get("api_ca_file")
    if api_ca_file is not None:
        api_ca_file = _require_str(api_ca_file, context, "api_ca_file")
    ssh_port = _optional_int(router.get("ssh_port"), context, "ssh_port", 22)
    ssh_known_hosts = router.get("ssh_known_hosts")
    if ssh_known_hosts is None:
        ssh_known_hosts = "~/.ssh/known_hosts"
    else:
        ssh_known_hosts = _require_str(
            ssh_known_hosts, context, "ssh_known_hosts"
        )

    password = os.environ.get(password_env)
    if password is None or not password.strip():
        raise ConfigError(
            f"{context}.password_env: environment variable {password_env!r} "
            f"for router {name!r} is unset or empty"
        )

    return RouterConfig(
        name=name,
        host=host,
        username=username,
        password_env=password_env,
        api_port=api_port,
        api_tls=api_tls,
        api_ca_file=api_ca_file,
        ssh_port=ssh_port,
        ssh_known_hosts=ssh_known_hosts,
    )


def _load_telegram(raw: Any, context: str) -> Optional[TelegramConfig]:
    if raw is None:
        return None
    telegram = _require_mapping(raw, context)
    token_env = telegram.get("token_env")
    chat_id = telegram.get("chat_id")
    if token_env is None and chat_id is None:
        return None
    if token_env is None or chat_id is None:
        raise ConfigError(
            f"{context}: token_env and chat_id must be set together"
        )
    token_env = _require_str(token_env, context, "token_env")
    chat_id = _require_str(chat_id, context, "chat_id")
    return TelegramConfig(token_env=token_env, chat_id=chat_id)


def load_config(path: str | Path) -> AppConfig:
    """Load and validate the inventory YAML file at ``path``.

    Passwords are read only from the environment variable named by each
    router's ``password_env`` field; they never appear in the YAML or logs.
    """
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except IsADirectoryError as exc:
        raise ConfigError(f"config path is a directory: {path}") from exc
    except PermissionError as exc:
        raise ConfigError(f"permission denied reading config: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    if data is None:
        raise ConfigError(f"{path}: document is empty")
    top = _require_mapping(data, str(path))

    backup_dir = top.get("backup_dir", "backups")
    if not isinstance(backup_dir, str) or not backup_dir.strip():
        backup_dir = "backups"

    raw_routers = top.get("routers")
    if raw_routers is None:
        raise ConfigError(f"{path}: 'routers' is required and must be non-empty")
    if not isinstance(raw_routers, list) or len(raw_routers) == 0:
        raise ConfigError(f"{path}: 'routers' must be a non-empty list")

    routers = [_load_router(raw, i) for i, raw in enumerate(raw_routers)]

    telegram = _load_telegram(top.get("telegram"), "telegram")

    return AppConfig(
        backup_dir=backup_dir,
        routers=routers,
        telegram=telegram,
    )
