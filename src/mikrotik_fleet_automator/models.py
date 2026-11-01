"""Data models for MikroTik fleet automator."""

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


@dataclass(frozen=True)
class TelegramConfig:
    """Optional Telegram notification settings."""

    token_env: Optional[str] = None
    chat_id: Optional[str] = None


@dataclass(frozen=True)
class AppConfig:
    """Full application configuration loaded from YAML."""

    backup_dir: str
    routers: list[RouterConfig]
    telegram: Optional[TelegramConfig] = None
