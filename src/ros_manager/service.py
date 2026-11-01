"""Per-router check/backup/doctor service with error isolation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Optional

from .config import AppConfig
from .models import RouterConfig, RouterDoctor, RouterHealth
from .router import RouterClient, RouterError
from .storage import prune_backups, write_backup


class RouterSelectionError(Exception):
    """Raised when a --router/--group selector matches nothing known."""


@dataclass
class BackupResult:
    """Result of backing up a single router."""

    name: str
    host: str
    status: str  # "ok" | "error"
    error: Optional[str] = None
    path: Optional[str] = None
    pruned: int = 0


@dataclass
class RouterResult:
    """Combined check + optional backup result for one router."""

    name: str
    host: str
    health: Optional[RouterHealth] = None
    backup: Optional[BackupResult] = None


# -- router selection ----------------------------------------------------


def select_routers(
    routers: Iterable[RouterConfig],
    names: Optional[Iterable[str]] = None,
    groups: Optional[Iterable[str]] = None,
) -> list[RouterConfig]:
    """Return routers matching any of the given names or groups.

    Routers without an explicit ``groups`` entry belong to the implicit
    ``default`` group. Unknown names or groups raise
    :class:`RouterSelectionError` so typos never silently select nothing.
    """
    routers = list(routers)
    names = [n for n in (names or []) if n]
    groups = [g for g in (groups or []) if g]
    if not names and not groups:
        return routers

    known_names = {r.name for r in routers}
    known_groups = {g for r in routers for g in (r.groups or ("default",))}
    unknown_names = sorted(set(names) - known_names)
    unknown_groups = sorted(set(groups) - known_groups)
    if unknown_names or unknown_groups:
        parts = []
        if unknown_names:
            parts.append("unknown router(s): " + ", ".join(unknown_names))
        if unknown_groups:
            parts.append("unknown group(s): " + ", ".join(unknown_groups))
        raise RouterSelectionError("; ".join(parts))

    selected: list[RouterConfig] = []
    for router in routers:
        router_groups = router.groups or ("default",)
        if (names and router.name in names) or (
            groups and any(group in groups for group in router_groups)
        ):
            selected.append(router)
    return selected


def filter_config(
    config: AppConfig,
    names: Optional[Iterable[str]] = None,
    groups: Optional[Iterable[str]] = None,
) -> AppConfig:
    """Return a copy of ``config`` limited to the selected routers."""
    return replace(config, routers=select_routers(config.routers, names, groups))


# -- per-router operations -----------------------------------------------


def check_router(config) -> RouterHealth:
    """Run a health check for one router; failures are captured in the result."""
    client = RouterClient(config)
    return client.get_health()


def doctor_router(config) -> RouterDoctor:
    """Run an extended diagnostic for one router."""
    client = RouterClient(config)
    return client.get_doctor()


def _effective_keep_last(config, keep_last: Optional[int]) -> Optional[int]:
    if config.retention_keep_last is not None:
        return config.retention_keep_last
    return keep_last


def backup_router(
    config, backup_dir: str, keep_last: Optional[int] = None
) -> BackupResult:
    """Export config for one router, write it atomically, then prune old copies."""
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
    pruned = 0
    effective_keep = _effective_keep_last(config, keep_last)
    if effective_keep is not None:
        pruned = len(prune_backups(backup_dir, config.name, effective_keep))
    return BackupResult(
        name=config.name,
        host=config.host,
        status="ok",
        path=str(path),
        pruned=pruned,
    )


def run_router(
    config,
    backup_dir: str,
    do_check: bool,
    do_backup: bool,
    keep_last: Optional[int] = None,
) -> RouterResult:
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
        backup = backup_router(config, backup_dir, keep_last)

    return RouterResult(
        name=config.name,
        host=config.host,
        health=health,
        backup=backup,
    )


def run_inventory(config: AppConfig, do_check: bool, do_backup: bool) -> list[RouterResult]:
    """Run check and/or backup on every router; failures never stop the run."""
    return [
        run_router(
            router,
            config.backup_dir,
            do_check,
            do_backup,
            config.retention_keep_last,
        )
        for router in config.routers
    ]


def run_doctor_inventory(config: AppConfig) -> list[RouterDoctor]:
    """Run the extended diagnostic on every router, isolating failures."""
    results: list[RouterDoctor] = []
    for router in config.routers:
        try:
            results.append(doctor_router(router))
        except RouterError as exc:
            results.append(
                RouterDoctor(
                    name=router.name,
                    host=router.host,
                    status="error",
                    error=str(exc),
                )
            )
    return results


def any_failure(results: list[RouterResult]) -> bool:
    """True if any router check or backup failed."""
    for result in results:
        if result.health is not None and result.health.status == "error":
            return True
        if result.backup is not None and result.backup.status == "error":
            return True
    return False


def any_doctor_failure(results: list[RouterDoctor]) -> bool:
    """True if any doctor diagnostic failed."""
    return any(result.status == "error" for result in results)
