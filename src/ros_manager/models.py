"""Data models for ROS Manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RouterInterface:
    """A single RouterOS interface as reported by /interface/print."""

    name: str
    type: Optional[str]
    running: Optional[bool]
    disabled: Optional[bool]


@dataclass(frozen=True)
class RouterHealth:
    """Health snapshot for a single router."""

    name: str
    host: str
    status: str  # "ok" | "error"
    error: Optional[str] = None
    temperature_c: Optional[float] = None
    cpu_load_percent: Optional[float] = None
    memory_total_bytes: Optional[int] = None
    memory_free_bytes: Optional[int] = None
    interfaces: list[RouterInterface] = field(default_factory=list)


@dataclass(frozen=True)
class RouterDoctor:
    """Extended diagnostic snapshot for a single router."""

    name: str
    host: str
    status: str  # "ok" | "error"
    error: Optional[str] = None
    version: Optional[str] = None
    uptime: Optional[str] = None
    board_name: Optional[str] = None
    architecture: Optional[str] = None
    cpu_count: Optional[int] = None
    disk_total_bytes: Optional[int] = None
    disk_free_bytes: Optional[int] = None
    temperature_c: Optional[float] = None
    voltage: Optional[float] = None
    fan_speed: Optional[float] = None
    latency_ms: Optional[float] = None


@dataclass(frozen=True)
class RouterConfig:
    """Inventory entry for a single MikroTik router."""

    name: str
    host: str
    username: str
    password_env: str
    api_port: int = 8729
    api_tls: bool = True
    api_ca_file: Optional[str] = None
    ssh_port: int = 22
    ssh_known_hosts: str = "~/.ssh/known_hosts"
    groups: tuple[str, ...] = ()
    retention_keep_last: Optional[int] = None


@dataclass(frozen=True)
class TelegramConfig:
    """Optional Telegram notification settings."""

    token_env: Optional[str] = None
    chat_id: Optional[str] = None


@dataclass(frozen=True)
class WebhookConfig:
    """Optional generic webhook notification settings."""

    url_env: str
    style: str = "generic"  # generic | slack | discord


@dataclass(frozen=True)
class NotificationsConfig:
    """Notification channels; either or both may be configured."""

    telegram: Optional[TelegramConfig] = None
    webhook: Optional[WebhookConfig] = None


@dataclass(frozen=True)
class AppConfig:
    """Full application configuration loaded from YAML."""

    backup_dir: str
    routers: list[RouterConfig]
    telegram: Optional[TelegramConfig] = None
    retention_keep_last: Optional[int] = None
    notifications: Optional[NotificationsConfig] = None
    state_file: str = ".rosm_state.json"
