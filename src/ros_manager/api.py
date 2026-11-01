"""FastAPI application: JSON backup API plus a small live dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .config import ConfigError, load_config
from .models import AppConfig
from .report import render_dashboard, render_error_page
from .serialize import generated_at, health_entry, run_entry
from .service import (
    RouterResult,
    RouterSelectionError,
    filter_config,
    run_inventory,
)


def _run_payload(results: list[RouterResult]) -> dict:
    return {
        "generated_at": generated_at(),
        "routers": [run_entry(result) for result in results],
    }


def _status_payload(results: list[RouterResult]) -> dict:
    return {
        "generated_at": generated_at(),
        "routers": [health_entry(result) for result in results],
    }


def _backup_results(config: AppConfig) -> list[RouterResult]:
    return run_inventory(config, do_check=False, do_backup=True)


def _config_failed_app(message: str) -> FastAPI:
    """Build an app whose endpoints all report the same safe config error.

    The message comes from :class:`ConfigError`, which never contains secrets,
    so it is safe to return to the client.
    """
    app = FastAPI(title="ROS Manager")
    detail = f"config error: {message}"

    def json_error() -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": detail})

    def html_error() -> HTMLResponse:
        return HTMLResponse(
            status_code=500, content=render_error_page(detail)
        )

    app.add_api_route("/", html_error, methods=["GET"])
    app.add_api_route("/api/status", json_error, methods=["GET"])
    app.add_api_route("/api/backups", json_error, methods=["POST"])
    app.add_api_route("/backups", json_error, methods=["POST"])
    app.add_api_route("/api/backups/{name}", json_error, methods=["POST"])
    return app


def create_app(config_path: str | Path) -> FastAPI:
    """Create the FastAPI app backed by the inventory at ``config_path``.

    Configuration load/validation failures yield HTTP 500 with a safe message
    (no secrets or tokens in the response) for every endpoint.
    """
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        return _config_failed_app(str(exc))

    app = FastAPI(title="ROS Manager")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=render_dashboard(config))

    @app.get("/api/status")
    async def status() -> JSONResponse:
        results = run_inventory(config, do_check=True, do_backup=False)
        # HTTP 200 even when routers are unreachable; per-router status carries it.
        return JSONResponse(status_code=200, content=_status_payload(results))

    @app.post("/api/backups")
    async def backups() -> JSONResponse:
        results = _backup_results(config)
        return JSONResponse(status_code=200, content=_run_payload(results))

    # Legacy endpoint kept for existing clients.
    @app.post("/backups")
    async def backups_legacy() -> JSONResponse:
        results = _backup_results(config)
        return JSONResponse(status_code=200, content=_run_payload(results))

    @app.post("/api/backups/{name}")
    async def backup_one(name: str) -> JSONResponse:
        try:
            scoped = filter_config(config, [name])
        except RouterSelectionError as exc:
            return JSONResponse(status_code=404, content={"detail": str(exc)})
        results = _backup_results(scoped)
        return JSONResponse(status_code=200, content=_run_payload(results))

    return app
