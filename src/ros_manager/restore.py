"""Local backup verification and SSH-based restore."""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import paramiko

from .config import AppConfig
from .models import RouterConfig
from .storage import latest_backup


class RestoreError(Exception):
    """Raised when a restore plan or upload cannot be prepared/performed."""


_SECTION_RE = re.compile(r"^/[A-Za-z]", re.MULTILINE)


def verify_backup_file(
    path: str | Path, max_age_days: Optional[int] = None
) -> list[str]:
    """Return problems with a local backup file; an empty list means valid.

    Raises ``OSError`` if the file cannot be read and ``UnicodeDecodeError``
    if it is not valid UTF-8.
    """
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"backup file not found: {target}")

    text = target.read_text(encoding="utf-8-sig")
    problems: list[str] = []
    if not text.strip():
        problems.append("file is empty")
    if not _SECTION_RE.search(text):
        problems.append(
            "no RouterOS configuration sections found "
            "(expected lines starting with '/')"
        )
    if max_age_days is not None:
        age_seconds = datetime.now(timezone.utc).timestamp() - target.stat().st_mtime
        age_days = age_seconds / 86400
        if age_days > max_age_days:
            problems.append(
                f"backup is {age_days:.1f} days old (limit {max_age_days})"
            )
    return problems


@dataclass(frozen=True)
class RestorePlan:
    """What a restore would do, without touching the router."""

    router: RouterConfig
    file: Path
    size: int
    preview: list[str]
    latest: Optional[Path]
    diff: str


def plan_restore(
    config: AppConfig, router_name: str, file: str | Path
) -> RestorePlan:
    """Build a dry-run restore plan; never connects to the router."""
    router = next((r for r in config.routers if r.name == router_name), None)
    if router is None:
        raise RestoreError(f"unknown router: {router_name!r}")

    target = Path(file)
    if not target.is_file():
        raise RestoreError(f"backup file not found: {target}")

    contents = target.read_text(encoding="utf-8")
    preview = contents.splitlines()[:10]

    latest = latest_backup(config.backup_dir, router_name)
    diff = ""
    if latest is not None:
        old_lines = latest.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = contents.splitlines(keepends=True)
        diff = "".join(
            difflib.unified_diff(
                old_lines, new_lines, fromfile=str(latest), tofile=str(target)
            )
        )

    return RestorePlan(
        router=router,
        file=target,
        size=target.stat().st_size,
        preview=preview,
        latest=latest,
        diff=diff,
    )


def _connect(router: RouterConfig) -> paramiko.SSHClient:
    password = os.environ.get(router.password_env, "")
    if not password.strip():
        raise RestoreError(
            f"environment variable {router.password_env!r} for router "
            f"{router.name!r} is unset or empty"
        )

    client = paramiko.SSHClient()
    known_hosts = os.path.expanduser(router.ssh_known_hosts)
    if os.path.isfile(known_hosts):
        client.load_host_keys(known_hosts)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(
            hostname=router.host,
            port=router.ssh_port,
            username=router.username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=10,
        )
    except (paramiko.SSHException, OSError) as exc:
        client.close()
        raise RestoreError(f"SSH connection error: {exc}") from exc
    return client


def apply_restore(router: RouterConfig, file: str | Path) -> str:
    """Upload a backup via SFTP and run ``/import``; never reboots.

    Returns the remote filename that was imported.
    """
    target = Path(file)
    if not target.is_file():
        raise RestoreError(f"backup file not found: {target}")

    remote_name = (
        "rosm-restore-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + ".rsc"
    )

    client = _connect(router)
    try:
        try:
            sftp = client.open_sftp()
        except paramiko.SSHException as exc:
            raise RestoreError(f"SFTP error: {exc}") from exc
        try:
            sftp.put(str(target), remote_name)
        finally:
            sftp.close()

        _, stdout, stderr = client.exec_command(f"/import file={remote_name}")
        output = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace")
        status = stdout.channel.recv_exit_status()
        if status != 0:
            detail = (error or output).strip()
            raise RestoreError(f"/import failed (exit {status}): {detail}")
        return remote_name
    finally:
        client.close()
