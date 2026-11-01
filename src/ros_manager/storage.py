"""Atomic, timestamped backup storage."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def backup_filename(router_name: str) -> str:
    """Return ``{router_name}_{UTC timestamp}.rsc`` with microsecond precision."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{router_name}_{stamp}.rsc"


def write_backup(backup_dir: str | Path, router_name: str, contents: str) -> Path:
    """Write backup contents atomically and return the final path.

    Writes to a temp file in the same directory then ``os.replace`` so an
    interrupted process never leaves a partial `.rsc` behind.
    """
    directory = Path(backup_dir)
    directory.mkdir(parents=True, exist_ok=True)

    target = directory / backup_filename(router_name)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(directory), prefix=f".{target.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(contents)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    return target


def list_backups(backup_dir: str | Path, router_name: str) -> list[Path]:
    """Return backups for ``router_name`` sorted oldest to newest."""
    directory = Path(backup_dir)
    if not directory.is_dir():
        return []
    prefix = f"{router_name}_"
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name.startswith(prefix)
        and path.name.endswith(".rsc")
    )


def latest_backup(backup_dir: str | Path, router_name: str) -> Optional[Path]:
    """Return the newest backup for ``router_name``, or None."""
    files = list_backups(backup_dir, router_name)
    return files[-1] if files else None


def prune_backups(
    backup_dir: str | Path, router_name: str, keep_last: int | None
) -> list[Path]:
    """Delete the oldest backups for ``router_name`` beyond ``keep_last``.

    Files are matched by the ``{router_name}_*.rsc`` naming convention and
    ordered by filename, which sorts chronologically because timestamps are
    fixed-width UTC. Returns the deleted paths.
    """
    if keep_last is None or keep_last < 1:
        return []
    directory = Path(backup_dir)
    if not directory.is_dir():
        return []

    prefix = f"{router_name}_"
    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name.startswith(prefix)
        and path.name.endswith(".rsc")
    )
    excess = len(files) - keep_last
    if excess <= 0:
        return []

    deleted: list[Path] = []
    for path in files[:excess]:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        deleted.append(path)
    return deleted
