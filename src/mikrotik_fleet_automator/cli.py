"""Typer CLI: check, backup, run, diff, schedule, serve."""

from __future__ import annotations

import csv
import difflib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from .api import create_app
from .config import ConfigError, load_config
from .models import AppConfig
from .router import RouterError
from .scheduler import run_schedule
from .service import RouterResult, any_failure, run_inventory
from .storage import write_backup
from .telegram import resolve_telegram, send_summary

app = typer.Typer(
    name="mfa",
    help="MikroTik fleet automator: health check, backup, diff, and scheduler.",
)

_NO_VALUE = ""  # sentinel for options not provided on the command line


# -- helpers -------------------------------------------------------------

def _load(path: str) -> AppConfig:
    if not path:
        typer.secho("--config is required", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    try:
        return load_config(path)
    except ConfigError as exc:
        typer.secho(f"config error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc


def _generated_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _health_entry(result: RouterResult) -> dict:
    health = result.health
    if health is None:
        return {
            "name": result.name,
            "host": result.host,
            "status": "error",
            "error": "check not performed",
            "temperature_c": None,
            "cpu_load_percent": None,
            "memory_total_bytes": None,
            "memory_free_bytes": None,
            "interfaces": [],
        }
    return {
        "name": health.name,
        "host": health.host,
        "status": health.status,
        "error": health.error,
        "temperature_c": health.temperature_c,
        "cpu_load_percent": health.cpu_load_percent,
        "memory_total_bytes": health.memory_total_bytes,
        "memory_free_bytes": health.memory_free_bytes,
        "interfaces": [
            {
                "name": iface.name,
                "type": iface.type,
                "running": iface.running,
                "disabled": iface.disabled,
            }
            for iface in health.interfaces
        ],
    }


def _run_entry(result: RouterResult) -> dict:
    entry = _health_entry(result)
    backup = result.backup
    if backup is None:
        entry["backup"] = {"status": "skipped", "error": None, "path": None}
    else:
        entry["backup"] = {
            "status": backup.status,
            "error": backup.error,
            "path": backup.path,
        }
    if entry["status"] == "ok" and backup is not None and backup.status == "error":
        entry["status"] = "error"
        entry["error"] = backup.error or entry["error"]
    return entry


def _interfaces_up_total(health) -> tuple[Optional[int], Optional[int]]:
    if health is None:
        return None, None
    up = None
    total = None
    if health.interfaces is not None:
        total = len(health.interfaces)
        up = sum(1 for i in health.interfaces if i.running is True)
    return up, total


def _write_output(payload: str, output: str) -> None:
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        typer.echo(payload)


def _format_text(results: list[RouterResult], include_backup: bool) -> str:
    lines: list[str] = []
    for result in results:
        health = result.health
        if health is None:
            lines.append(f"{result.name} ({result.host}): error - check not performed")
            continue
        parts = [f"{result.name} ({result.host}): {health.status}"]
        if health.temperature_c is not None:
            parts.append(f"temp={health.temperature_c}°C")
        if health.cpu_load_percent is not None:
            parts.append(f"cpu={health.cpu_load_percent}%")
        if health.memory_total_bytes is not None:
            parts.append(f"mem={health.memory_free_bytes}/{health.memory_total_bytes}B")
        if health.interfaces is not None:
            up = sum(1 for i in health.interfaces if i.running is True)
            parts.append(f"if={up}/{len(health.interfaces)}")
        if health.error:
            parts.append(f"error={health.error}")
        lines.append(" - ".join(parts))
        if include_backup:
            backup = result.backup
            if backup is None:
                lines.append("  backup: skipped")
            else:
                bparts = [f"  backup: {backup.status}"]
                if backup.path:
                    bparts.append(f"path={backup.path}")
                if backup.error:
                    bparts.append(f"error={backup.error}")
                lines.append(" - ".join(bparts))
    errors = [
        r
        for r in results
        if (r.health and r.health.status == "error")
        or (r.backup and r.backup.status == "error")
    ]
    if errors:
        lines.append("")
        lines.append("Errors:")
        for result in errors:
            detail = []
            if result.health and result.health.error:
                detail.append(f"check: {result.health.error}")
            if result.backup and result.backup.error:
                detail.append(f"backup: {result.backup.error}")
            lines.append(f"  - {result.name} ({result.host}): {'; '.join(detail)}")
    return "\n".join(lines) + "\n"


def _format_json(results: list[RouterResult], include_backup: bool) -> str:
    payload = {
        "generated_at": _generated_at(),
        "routers": [_run_entry(r) if include_backup else _health_entry(r) for r in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _format_csv(results: list[RouterResult], include_backup: bool) -> str:
    buf = io.StringIO()
    if include_backup:
        fieldnames = [
            "name", "host", "status", "temperature_c", "cpu_load_percent",
            "memory_total_bytes", "memory_free_bytes", "interfaces_up",
            "interfaces_total", "error", "backup_status", "backup_error",
            "backup_path",
        ]
    else:
        fieldnames = [
            "name", "host", "status", "temperature_c", "cpu_load_percent",
            "memory_total_bytes", "memory_free_bytes", "interfaces_up",
            "interfaces_total", "error",
        ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for result in results:
        health = result.health
        up, total = _interfaces_up_total(health)
        row = {
            "name": result.name,
            "host": result.host,
            "status": health.status if health else "error",
            "temperature_c": health.temperature_c if health else None,
            "cpu_load_percent": health.cpu_load_percent if health else None,
            "memory_total_bytes": health.memory_total_bytes if health else None,
            "memory_free_bytes": health.memory_free_bytes if health else None,
            "interfaces_up": up,
            "interfaces_total": total,
            "error": health.error if health else "check not performed",
        }
        if include_backup:
            backup = result.backup
            row["backup_status"] = backup.status if backup else "skipped"
            row["backup_error"] = backup.error if backup else None
            row["backup_path"] = backup.path if backup else None
        writer.writerow(row)
    return buf.getvalue()


def _handle_results(
    results: list[RouterResult], fmt: str, output: str, include_backup: bool
) -> int:
    if fmt == "text":
        payload = _format_text(results, include_backup)
    elif fmt == "json":
        payload = _format_json(results, include_backup)
    elif fmt == "csv":
        payload = _format_csv(results, include_backup)
    else:  # pragma: no cover - validated by caller
        typer.secho(f"unknown format: {fmt}", err=True, fg=typer.colors.RED)
        return 2
    _write_output(payload, output)
    return 1 if any_failure(results) else 0


def _notify_telegram(config: AppConfig, results: list[RouterResult]) -> None:
    """Send run summary to Telegram; raises on invalid config/token."""
    telegram = resolve_telegram(config)
    if telegram is None:
        return
    lines = [f"*MikroTik run summary* ({len(results)} router(s))"]
    for result in results:
        health = result.health
        backup = result.backup
        h = f"check={health.status}" if health else "check=skipped"
        if health and health.error:
            h += f" ({health.error})"
        b = f"backup={backup.status}" if backup else "backup=skipped"
        if backup and backup.error:
            b += f" ({backup.error})"
        lines.append(f"- {result.name} ({result.host}): {h}, {b}")
    send_summary(telegram, telegram.chat_id, "\n".join(lines))


# -- commands ------------------------------------------------------------

@app.command()
def check(
    config: str = typer.Option(_NO_VALUE, "--config", help="Path to inventory YAML."),
    format: str = typer.Option("text", "--format", help="Output format: text, json, csv."),
    output: str = typer.Option(_NO_VALUE, "--output", help="Write output to file instead of terminal."),
) -> None:
    """Health check every router in the inventory."""
    cfg = _load(config)
    fmt = format.lower()
    if fmt not in {"text", "json", "csv"}:
        typer.secho(f"invalid format: {format}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    results = run_inventory(cfg, do_check=True, do_backup=False)
    raise typer.Exit(_handle_results(results, fmt, output, include_backup=False))


@app.command()
def backup(
    config: str = typer.Option(_NO_VALUE, "--config", help="Path to inventory YAML."),
) -> None:
    """Back up configuration of every router."""
    cfg = _load(config)
    results = run_inventory(cfg, do_check=False, do_backup=True)
    payload = _format_text(results, include_backup=True)
    typer.echo(payload)
    raise typer.Exit(1 if any_failure(results) else 0)


@app.command()
def run(
    config: str = typer.Option(_NO_VALUE, "--config", help="Path to inventory YAML."),
    format: str = typer.Option("text", "--format", help="Output format: text, json, csv."),
    output: str = typer.Option(_NO_VALUE, "--output", help="Write output to file instead of terminal."),
    notify: bool = typer.Option(False, "--notify", help="Send Telegram summary after the run.", is_flag=True),
) -> None:
    """Check and back up every router, then summarize both."""
    cfg = _load(config)
    fmt = format.lower()
    if fmt not in {"text", "json", "csv"}:
        typer.secho(f"invalid format: {format}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    results = run_inventory(cfg, do_check=True, do_backup=True)
    exit_code = _handle_results(results, fmt, output, include_backup=True)
    if notify:
        try:
            _notify_telegram(cfg, results)
        except Exception as exc:  # noqa: BLE001 - surface as CLI error
            typer.secho(f"telegram error: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1) from exc
    raise typer.Exit(exit_code)


@app.command()
def diff(
    old: str = typer.Argument(..., help="Path to old backup .rsc file."),
    new: str = typer.Argument(..., help="Path to new backup .rsc file."),
) -> None:
    """Print unified diff between two backup files; exit 0 if same, 1 if different."""
    try:
        old_lines = Path(old).read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = Path(new).read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        typer.secho(f"error reading backup file: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc
    diff_lines = list(
        difflib.unified_diff(old_lines, new_lines, fromfile=old, tofile=new)
    )
    import sys

    if diff_lines:
        sys.stdout.write("".join(diff_lines))
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command()
def schedule(
    config: str = typer.Option(_NO_VALUE, "--config", help="Path to inventory YAML."),
    interval_seconds: int = typer.Option(..., "--interval-seconds", help="Interval between runs in seconds."),
) -> None:
    """Run `run` immediately, then repeat every interval until stopped."""
    cfg = _load(config)
    if interval_seconds <= 0:
        typer.secho("interval_seconds must be positive", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    import threading

    stop_event = threading.Event()
    try:
        run_schedule(cfg, interval_seconds, stop_event=stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    raise typer.Exit(0)


@app.command()
def serve(
    config: str = typer.Option(_NO_VALUE, "--config", help="Path to inventory YAML."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address."),
    port: int = typer.Option(8000, "--port", help="Port to listen on."),
) -> None:
    """Run the FastAPI backup server with Uvicorn."""
    cfg = _load(config)
    import uvicorn

    app_api = create_app(config)
    uvicorn.run(app_api, host=host, port=port)
