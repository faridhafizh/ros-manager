"""YAML configuration loading and validation."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Optional

import yaml

from .models import (
    AppConfig,
    NotificationsConfig,
    RouterConfig,
    TelegramConfig,
    WebhookConfig,
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


def _optional_positive_int(
    value: Any, context: str, field: str
) -> Optional[int]:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(
            f"{context}.{field}: expected an integer, got {type(value).__name__}"
        )
    if value < 1:
        raise ConfigError(f"{context}.{field}: must be >= 1")
    return value


def _optional_str_tuple(
    value: Any, context: str, field: str
) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError(
            f"{context}.{field}: expected a list, got {type(value).__name__}"
        )
    return tuple(
        _require_nonempty_str(item, context, f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _load_retention(raw: Any, context: str) -> Optional[int]:
    """Read an optional ``retention: {keep_last: N}`` block."""
    if raw is None:
        return None
    retention = _require_mapping(raw, context)
    return _optional_positive_int(retention.get("keep_last"), context, "keep_last")


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
    api_tls = _optional_bool(router.get("api_tls"), context, "api_tls", True)
    default_api_port = 8728 if not api_tls else 8729
    api_port = _optional_int(router.get("api_port"), context, "api_port", default_api_port)
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
    groups = _optional_str_tuple(router.get("groups"), context, "groups")
    retention_keep_last = _load_retention(
        router.get("retention"), f"{context}.retention"
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
        groups=groups,
        retention_keep_last=retention_keep_last,
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


def _load_webhook(raw: Any, context: str) -> Optional[WebhookConfig]:
    if raw is None:
        return None
    webhook = _require_mapping(raw, context)
    url_env = _require_nonempty_str(webhook.get("url_env"), context, "url_env")
    style = _require_str(webhook.get("style", "generic"), context, "style")
    if style not in {"generic", "slack", "discord"}:
        raise ConfigError(
            f"{context}.style: must be one of generic, slack, discord"
        )
    return WebhookConfig(url_env=url_env, style=style)


def _load_notifications(raw: Any, context: str) -> Optional[NotificationsConfig]:
    if raw is None:
        return None
    notifications = _require_mapping(raw, context)
    telegram = _load_telegram(
        notifications.get("telegram"), f"{context}.telegram"
    )
    webhook = _load_webhook(
        notifications.get("webhook"), f"{context}.webhook"
    )
    if telegram is None and webhook is None:
        return None
    return NotificationsConfig(telegram=telegram, webhook=webhook)


# -- multi-file inventories ----------------------------------------------


def _load_include_patterns(raw: Any, context: str) -> list[str]:
    """Read an optional ``include:`` string or list of glob patterns."""
    if raw is None:
        return []
    if isinstance(raw, str):
        items: list[Any] = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        raise ConfigError(
            f"{context}.include: expected a string or a list of strings"
        )
    return [
        _require_nonempty_str(item, context, f"include[{index}]")
        for index, item in enumerate(items)
    ]


def _expand_include(pattern: str, base: Path) -> list[Path]:
    """Expand one include pattern relative to ``base`` into existing files."""
    candidate = Path(pattern)
    if not candidate.is_absolute():
        candidate = base / candidate
    matches = sorted(Path(match) for match in glob.glob(str(candidate)))
    if not matches:
        raise ConfigError(f"include not found: {pattern}")
    files = [match for match in matches if match.is_file()]
    if not files:
        raise ConfigError(f"include is not a file: {pattern}")
    return files


def _read_document(path: Path) -> dict[str, Any]:
    """Read and parse one YAML file, raising ConfigError on any problem."""
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
    return _require_mapping(data, str(path))


def _collect_routers(
    path: Path, top: dict[str, Any], stack: tuple[Path, ...]
) -> list[RouterConfig]:
    """Collect routers from ``path`` plus every file it includes, recursively."""
    routers: list[RouterConfig] = []

    raw_routers = top.get("routers")
    if raw_routers is not None:
        if not isinstance(raw_routers, list):
            raise ConfigError(f"{path}: 'routers' must be a list")
        routers.extend(
            _load_router(raw, index) for index, raw in enumerate(raw_routers)
        )

    for pattern in _load_include_patterns(top.get("include"), str(path)):
        for included in _expand_include(pattern, path.parent):
            resolved = included.resolve()
            if resolved in stack:
                chain = " -> ".join(str(item) for item in stack + (resolved,))
                raise ConfigError(f"include cycle detected: {chain}")
            included_top = _read_document(included)
            routers.extend(
                _collect_routers(included, included_top, stack + (resolved,))
            )

    return routers


def load_config(path: str | Path) -> AppConfig:
    """Load and validate the inventory YAML file at ``path``.

    ``routers`` may be defined in the root file, in files listed under
    ``include:`` (a path or glob, relative to the including file), or both.
    Includes are recursive and cycles are reported as config errors.

    Passwords are read only from the environment variable named by each
    router's ``password_env`` field; they never appear in the YAML or logs.
    """
    path = Path(path)
    top = _read_document(path)

    backup_dir = top.get("backup_dir", "backups")
    if not isinstance(backup_dir, str) or not backup_dir.strip():
        backup_dir = "backups"

    routers = _collect_routers(path, top, (path.resolve(),))
    if not routers:
        raise ConfigError(
            f"{path}: no routers defined: 'routers' is required and must be "
            "non-empty (or add 'include' files)"
        )

    seen: set[str] = set()
    for router in routers:
        if router.name in seen:
            raise ConfigError(f"duplicate router name: {router.name!r}")
        seen.add(router.name)

    telegram = _load_telegram(top.get("telegram"), "telegram")
    retention_keep_last = _load_retention(top.get("retention"), "retention")
    notifications = _load_notifications(
        top.get("notifications"), "notifications"
    )

    state_file = top.get("state_file", ".rosm_state.json")
    if not isinstance(state_file, str) or not state_file.strip():
        raise ConfigError("state_file: must be a non-empty string")

    metrics_db = top.get("metrics_db", "metrics.db")
    if not isinstance(metrics_db, str) or not metrics_db.strip():
        raise ConfigError("metrics_db: must be a non-empty string")

    return AppConfig(
        backup_dir=backup_dir,
        routers=routers,
        telegram=telegram,
        retention_keep_last=retention_keep_last,
        notifications=notifications,
        state_file=state_file,
        metrics_db=metrics_db,
    )
