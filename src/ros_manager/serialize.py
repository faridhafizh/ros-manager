"""Shared JSON-serializable builders for CLI, API, and reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .models import RouterDoctor
from .service import RouterResult


def generated_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def health_entry(result: RouterResult) -> dict:
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


def run_entry(result: RouterResult) -> dict:
    entry = health_entry(result)
    backup = result.backup
    if backup is None:
        entry["backup"] = {"status": "skipped", "error": None, "path": None, "pruned": 0}
    else:
        entry["backup"] = {
            "status": backup.status,
            "error": backup.error,
            "path": backup.path,
            "pruned": backup.pruned,
        }
    if entry["status"] == "ok" and backup is not None and backup.status == "error":
        entry["status"] = "error"
        entry["error"] = backup.error or entry["error"]
    return entry


def interfaces_up_total(health) -> tuple[Optional[int], Optional[int]]:
    if health is None:
        return None, None
    up = None
    total = None
    if health.interfaces is not None:
        total = len(health.interfaces)
        up = sum(1 for i in health.interfaces if i.running is True)
    return up, total


def doctor_entry(result: RouterDoctor) -> dict:
    return {
        "name": result.name,
        "host": result.host,
        "status": result.status,
        "error": result.error,
        "version": result.version,
        "uptime": result.uptime,
        "board_name": result.board_name,
        "architecture": result.architecture,
        "cpu_count": result.cpu_count,
        "disk_total_bytes": result.disk_total_bytes,
        "disk_free_bytes": result.disk_free_bytes,
        "temperature_c": result.temperature_c,
        "voltage": result.voltage,
        "fan_speed": result.fan_speed,
        "latency_ms": result.latency_ms,
    }
