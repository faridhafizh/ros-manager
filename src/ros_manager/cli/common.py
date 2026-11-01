"""Shared helpers for the ROS Manager CLI commands."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Optional

import typer

from ..config import ConfigError, load_config
from ..models import AppConfig, RouterDoctor
from ..report import render_html_report
from ..serialize import (
    doctor_entry,
    generated_at,
    health_entry,
    interfaces_up_total,
    run_entry,
)
from ..service import (
    RouterResult,
    RouterSelectionError,
    any_doctor_failure,
    any_failure,
    filter_config,
)

NO_VALUE = ""  # sentinel for options not provided on the command line

VALID_FORMATS = {"text", "json", "csv"}
REPORT_FORMATS = VALID_FORMATS | {"html"}


def load_app_config(path: str) -> AppConfig:
    """Load the inventory YAML, exiting with code 2 on any config error."""
    if not path:
        typer.secho("--config is required", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    try:
        return load_config(path)
    except ConfigError as exc:
        typer.secho(f"config error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc


def resolve_format(value: str, allowed: Optional[set[str]] = None) -> str:
    """Validate and normalize an output format option.

    ``allowed`` defaults to the plain tabular formats; commands that can
    render a standalone report pass :data:`REPORT_FORMATS` to accept ``html``.
    """
    fmt = value.lower()
    allowed = allowed or VALID_FORMATS
    if fmt not in allowed:
        typer.secho(f"invalid format: {value}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    return fmt


def parse_list(value: str) -> list[str]:
    """Parse a comma-separated option value into stripped, non-empty items."""
    return [part.strip() for part in value.split(",") if part.strip()]


def select_config(config: AppConfig, router: str, group: str) -> AppConfig:
    """Apply --router/--group filters, exiting with code 2 on a bad selector."""
    try:
        return filter_config(config, parse_list(router), parse_list(group))
    except RouterSelectionError as exc:
        typer.secho(f"router selection error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc


def write_output(payload: str, output: str) -> None:
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        typer.echo(payload)


def format_text(results: list[RouterResult], include_backup: bool) -> str:
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
                if backup.pruned:
                    bparts.append(f"pruned={backup.pruned}")
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


def format_json(results: list[RouterResult], include_backup: bool) -> str:
    payload = {
        "generated_at": generated_at(),
        "routers": [run_entry(r) if include_backup else health_entry(r) for r in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def format_csv(results: list[RouterResult], include_backup: bool) -> str:
    buf = io.StringIO()
    if include_backup:
        fieldnames = [
            "name", "host", "status", "temperature_c", "cpu_load_percent",
            "memory_total_bytes", "memory_free_bytes", "interfaces_up",
            "interfaces_total", "error", "backup_status", "backup_error",
            "backup_path", "backup_pruned",
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
        up, total = interfaces_up_total(health)
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
            row["backup_pruned"] = backup.pruned if backup else 0
        writer.writerow(row)
    return buf.getvalue()


def format_html(results: list[RouterResult], include_backup: bool) -> str:
    title = "ROS Manager run report" if include_backup else "ROS Manager check report"
    return render_html_report(results, include_backup=include_backup, title=title)


def handle_results(
    results: list[RouterResult], fmt: str, output: str, include_backup: bool
) -> int:
    if fmt == "text":
        payload = format_text(results, include_backup)
    elif fmt == "json":
        payload = format_json(results, include_backup)
    elif fmt == "csv":
        payload = format_csv(results, include_backup)
    elif fmt == "html":
        payload = format_html(results, include_backup)
    else:  # pragma: no cover - validated by caller
        typer.secho(f"unknown format: {fmt}", err=True, fg=typer.colors.RED)
        return 2
    write_output(payload, output)
    return 1 if any_failure(results) else 0


# -- doctor output -------------------------------------------------------


def _mb(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    return f"{value / (1024 * 1024):.1f}MB"


def format_doctor_text(results: list[RouterDoctor]) -> str:
    lines: list[str] = []
    for result in results:
        if result.status == "error":
            lines.append(f"{result.name} ({result.host}): error - {result.error}")
            continue
        parts = [f"{result.name} ({result.host}): ok"]
        if result.version:
            parts.append(f"RouterOS {result.version}")
        if result.board_name:
            parts.append(f"board={result.board_name}")
        if result.architecture:
            parts.append(f"arch={result.architecture}")
        if result.cpu_count is not None:
            parts.append(f"cpu={result.cpu_count}")
        if result.uptime:
            parts.append(f"uptime={result.uptime}")
        disk_total = _mb(result.disk_total_bytes)
        disk_free = _mb(result.disk_free_bytes)
        if disk_total and disk_free:
            parts.append(f"disk={disk_free}/{disk_total}")
        if result.temperature_c is not None:
            parts.append(f"temp={result.temperature_c}°C")
        if result.voltage is not None:
            parts.append(f"voltage={result.voltage}V")
        if result.fan_speed is not None:
            parts.append(f"fan={result.fan_speed}")
        if result.latency_ms is not None:
            parts.append(f"latency={result.latency_ms}ms")
        lines.append(" - ".join(parts))
    return "\n".join(lines) + "\n"


def format_doctor_json(results: list[RouterDoctor]) -> str:
    payload = {
        "generated_at": generated_at(),
        "routers": [doctor_entry(r) for r in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def format_doctor_csv(results: list[RouterDoctor]) -> str:
    fieldnames = [
        "name", "host", "status", "version", "uptime", "board_name",
        "architecture", "cpu_count", "disk_total_bytes", "disk_free_bytes",
        "temperature_c", "voltage", "fan_speed", "latency_ms", "error",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for result in results:
        writer.writerow(doctor_entry(result))
    return buf.getvalue()


def handle_doctor_results(
    results: list[RouterDoctor], fmt: str, output: str
) -> int:
    if fmt == "text":
        payload = format_doctor_text(results)
    elif fmt == "json":
        payload = format_doctor_json(results)
    elif fmt == "csv":
        payload = format_doctor_csv(results)
    else:  # pragma: no cover - validated by caller
        typer.secho(f"unknown format: {fmt}", err=True, fg=typer.colors.RED)
        return 2
    write_output(payload, output)
    return 1 if any_doctor_failure(results) else 0

