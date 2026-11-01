"""Per-router check/backup service with error isolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import AppConfig
from .models import RouterHealth, RouterInterface
from .router import RouterClient, RouterError
from .storage import write_backup


@dataclass
class BackupResult:
    """Result of backing up a single router."""

    name: str
    host: str
    status: str  # "ok" | "error"
    error: Optional[str] = None
    path: Optional[str] = None


@dataclass
class RouterResult:
    """Combined check + optional backup result for one router."""

    name: str
    host: str
    health: Optional[RouterHealth] = None
    backup: Optional[BackupResult] = None


def check_router(config) -> RouterHealth:
    """Run a health check for one router; failures are captured in the result."""
    client = RouterClient(config)
    return client.get_health()


def backup_router(config, backup_dir: str) -> BackupResult:
    """Export config for one router and write it atomically."""
    client = RouterClient(config)
    try:
        contents = client.export_config()
    except RouterError as exc:
        return BackupResult(
            name=config.name,
            host=config.host,
            status="error",
            error=str(exc),
        )
    path = write_backup(backup_dir, config.name, contents)
    return BackupResult(
        name=config.name,
        host=config.host,
        status="ok",
        path=str(path),
    )


def run_router(config, backup_dir: str, do_check: bool, do_backup: bool) -> RouterResult:
    """Run check and/or backup for one router, isolating per-router failures."""
    health: Optional[RouterHealth] = None
    backup: Optional[BackupResult] = None

    if do_check:
        try:
            health = check_router(config)
        except RouterError as exc:
            health = RouterHealth(
                name=config.name,
                host=config.host,
                status="error",
                error=str(exc),
            )

    if do_backup:
        backup = backup_router(config, backup_dir)

    return RouterResult(
        name=config.name,
        host=config.host,
        health=health,
        backup=backup,
    )


def run_inventory(config: AppConfig, do_check: bool, do_backup: bool) -> list[RouterResult]:
    """Run check and/or backup on every router; failures never stop the run."""
    return [
        run_router(router, config.backup_dir, do_check, do_backup)
        for router in config.routers
    ]


def any_failure(results: list[RouterResult]) -> bool:
    """True if any router check or backup failed."""
    for result in results:
        if result.health is not None and result.health.status == "error":
            return True
        if result.backup is not None and result.backup.status == "error":
            return True
    return False
