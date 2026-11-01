"""Atomic, timestamped backup storage."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


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
