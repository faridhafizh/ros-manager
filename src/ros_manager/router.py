"""RouterOS connection adapter: API for health, SSH for config export.

RouterOS documentation states `/export` is CLI-only (not available via the
RouterOS API), so health checks use librouteros over the API while full
configuration backup is fetched over SSH with Paramiko. Connections are closed
on every exit path and per-router failures become displayable errors rather
than silent empty backups.
"""

from __future__ import annotations

import os
import ssl
import socket
import time
from typing import Optional

import librouteros
import paramiko
from librouteros.exceptions import LibRouterosError

from .models import RouterConfig, RouterDoctor, RouterHealth, RouterInterface


class RouterError(Exception):
    """Raised when a per-router connection or command fails."""


def _to_float(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_bool(value: object) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "running")
    return bool(value)


def _row_get(row: dict, key: str) -> object:
    try:
        return row.get(key)
    except AttributeError:
        return None


def _health_map(rows) -> dict[str, object]:
    """Flatten RouterOS health rows into a single name -> value mapping.

    RouterOS v7 may return either ``[{name: ..., value: ...}, ...]`` or a
    single row with one key per sensor; both shapes are supported.
    """
    data: dict[str, object] = {}
    for row in rows:
        name = _row_get(row, "name")
        value = _row_get(row, "value")
        if name is not None and value is not None:
            data[str(name)] = value
            continue
        try:
            for key, item in row.items():
                data[str(key)] = item
        except AttributeError:
            continue
    return data


def _first_float(data: dict, *keys: str) -> Optional[float]:
    for key in keys:
        value = _to_float(data.get(key))
        if value is not None:
            return value
    return None


class RouterClient:
    """Wraps API (health) and SSH (config export) connections for one router."""

    def __init__(self, config: RouterConfig) -> None:
        self.config = config

    # -- API: health -----------------------------------------------------

    def _api_password(self) -> str:
        password = os.environ.get(self.config.password_env, "")
        if not password.strip():
            raise RouterError(
                f"environment variable {self.config.password_env!r} for router "
                f"{self.config.name!r} is unset or empty"
            )
        return password

    def _make_ssl_wrapper(self, host: str):
        context = ssl.create_default_context(cafile=self.config.api_ca_file)

        def wrap(sock: socket.socket) -> ssl.SSLSocket:
            return context.wrap_socket(sock, server_hostname=host)

        return wrap

    def _connect_api(self):
        host = self.config.host
        port = self.config.api_port
        kwargs: dict = {
            "username": self.config.username,
            "password": self._api_password(),
            "host": host,
            "port": port,
        }
        if self.config.api_tls:
            kwargs["ssl_wrapper"] = self._make_ssl_wrapper(host)
        return librouteros.connect(**kwargs)

    def get_health(self) -> RouterHealth:
        """Return health snapshot; sensor/metric absence is null, not failure."""
        api = None
        try:
            api = self._connect_api()
            temperature_c = self._read_temperature(api)
            cpu_load, mem_total, mem_free = self._read_resource(api)
            interfaces = self._read_interfaces(api)
            return RouterHealth(
                name=self.config.name,
                host=self.config.host,
                status="ok",
                temperature_c=temperature_c,
                cpu_load_percent=cpu_load,
                memory_total_bytes=mem_total,
                memory_free_bytes=mem_free,
                interfaces=interfaces,
            )
        except RouterError:
            raise
        except LibRouterosError as exc:
            raise RouterError(f"API error: {exc}") from exc
        except OSError as exc:
            raise RouterError(f"connection error: {exc}") from exc
        finally:
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass

    def get_doctor(self) -> RouterDoctor:
        """Return extended diagnostics: version, board, disk, sensors, latency."""
        api = None
        try:
            api = self._connect_api()
            started = time.perf_counter()
            list(api("/system/identity/print"))
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            resource = self._read_resource_row(api)
            health = self._read_health(api)
            return RouterDoctor(
                name=self.config.name,
                host=self.config.host,
                status="ok",
                version=_optional_str(_row_get(resource, "version")),
                uptime=_optional_str(_row_get(resource, "uptime")),
                board_name=_optional_str(_row_get(resource, "board-name")),
                architecture=_optional_str(_row_get(resource, "architecture-name")),
                cpu_count=_to_int(_row_get(resource, "cpu-count")),
                disk_total_bytes=_to_int(_row_get(resource, "total-hdd-space")),
                disk_free_bytes=_to_int(_row_get(resource, "free-hdd-space")),
                temperature_c=_first_float(health, "temperature", "cpu-temperature"),
                voltage=_first_float(health, "voltage"),
                fan_speed=_first_float(health, "fan1-speed", "fan-speed", "fan-speed1"),
                latency_ms=latency_ms,
            )
        except RouterError:
            raise
        except LibRouterosError as exc:
            raise RouterError(f"API error: {exc}") from exc
        except OSError as exc:
            raise RouterError(f"connection error: {exc}") from exc
        finally:
            if api is not None:
                try:
                    api.close()
                except Exception:
                    pass

    def _read_temperature(self, api) -> Optional[float]:
        data = self._read_health(api)
        return _first_float(data, "temperature", "cpu-temperature")

    def _read_health(self, api) -> dict[str, object]:
        try:
            rows = list(api("/system/health/print"))
        except LibRouterosError:
            return {}
        return _health_map(rows)

    def _read_resource_row(self, api) -> dict:
        rows = list(api("/system/resource/print"))
        if not rows:
            return {}
        return rows[0]

    def _read_resource(self, api):
        row = self._read_resource_row(api)
        if not row:
            return None, None, None
        return (
            _to_float(_row_get(row, "cpu-load")),
            _to_int(_row_get(row, "total-memory")),
            _to_int(_row_get(row, "free-memory")),
        )

    def _read_interfaces(self, api) -> list[RouterInterface]:
        interfaces: list[RouterInterface] = []
        try:
            rows = list(api("/interface/print"))
        except LibRouterosError:
            return interfaces
        for row in rows:
            interfaces.append(
                RouterInterface(
                    name=str(_row_get(row, "name") or ""),
                    type=_optional_str(_row_get(row, "type")),
                    running=_to_bool(_row_get(row, "running")),
                    disabled=_to_bool(_row_get(row, "disabled")),
                )
            )
        return interfaces

    # -- SSH: config export ---------------------------------------------

    def export_config(self) -> str:
        """Fetch `/export terse` over SSH; never returns empty as success."""
        client = paramiko.SSHClient()
        try:
            known_hosts = os.path.expanduser(self.config.ssh_known_hosts)
            if os.path.isfile(known_hosts):
                client.load_host_keys(known_hosts)
            client.set_missing_host_key_policy(paramiko.RejectPolicy())

            password = self._api_password()
            client.connect(
                hostname=self.config.host,
                port=self.config.ssh_port,
                username=self.config.username,
                password=password,
                look_for_keys=False,
                allow_agent=False,
                timeout=10,
            )
            _, stdout, stderr = client.exec_command("/export terse")
            output = stdout.read().decode("utf-8")
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                detail = stderr.read().decode("utf-8", errors="replace").strip()
                raise RouterError(
                    f"/export terse failed (exit {exit_status}): {detail}"
                )
            return output
        except RouterError:
            raise
        except paramiko.SSHException as exc:
            raise RouterError(f"SSH error: {exc}") from exc
        except OSError as exc:
            raise RouterError(f"SSH connection error: {exc}") from exc
        finally:
            client.close()


def _optional_str(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)
