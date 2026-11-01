"""FastAPI application: JSON backup API plus a small live dashboard."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .auth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    SessionStore,
    auth_enabled,
    check_password,
)
from .config import ConfigError, load_config
from .metrics import load_history, prune_history, record_snapshot
from .models import AppConfig
from .report import render_dashboard, render_error_page, render_login_page
from .serialize import generated_at, health_entry, run_entry
from .service import (
    RouterResult,
    RouterSelectionError,
    filter_config,
    run_inventory,
)

#: Reuse a status result for this long so several dashboard tabs do not
#: hammer the routers with duplicate checks.
STATUS_CACHE_SECONDS = 10.0


def _run_payload(results: list[RouterResult], ts: Optional[str] = None) -> dict:
    return {
        "generated_at": ts or generated_at(),
        "routers": [run_entry(result) for result in results],
    }


def _status_payload(results: list[RouterResult], ts: Optional[str] = None) -> dict:
    return {
        "generated_at": ts or generated_at(),
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
    app.add_api_route("/login", html_error, methods=["GET", "POST"])
    app.add_api_route("/api/status", json_error, methods=["GET"])
    app.add_api_route("/api/history", json_error, methods=["GET"])
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

    prune_history(config.metrics_db)

    app = FastAPI(title="ROS Manager")
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="static",
    )
    sessions = SessionStore()
    status_cache: Optional[tuple[float, list[RouterResult], str]] = None

    def _authenticated(request: Request) -> bool:
        if not auth_enabled():
            return True
        return sessions.is_valid(request.cookies.get(SESSION_COOKIE))

    @app.middleware("http")
    async def _login_guard(request: Request, call_next):
        if request.url.path == "/login":
            return await call_next(request)
        if _authenticated(request):
            return await call_next(request)
        if request.method == "GET" and request.url.path == "/":
            return RedirectResponse(url="/login", status_code=303)
        return JSONResponse(status_code=401, content={"detail": "unauthorized"})

    def _current_status() -> tuple[list[RouterResult], str]:
        """Return status results, reusing a recent run for a few seconds."""
        nonlocal status_cache
        now = time.monotonic()
        if status_cache is not None and now - status_cache[0] < STATUS_CACHE_SECONDS:
            return status_cache[1], status_cache[2]
        results = run_inventory(config, do_check=True, do_backup=False)
        ts = generated_at()
        record_snapshot(config.metrics_db, ts, results)
        status_cache = (now, results, ts)
        return results, ts

    @app.get("/login", response_class=HTMLResponse)
    async def login_page() -> HTMLResponse:
        return HTMLResponse(content=render_login_page())

    @app.post("/login")
    async def login(request: Request):
        body = (await request.body())[:4096].decode("utf-8", "replace")
        password = parse_qs(body).get("password", [""])[0]
        if not check_password(password):
            return HTMLResponse(
                status_code=401,
                content=render_login_page("Incorrect password."),
            )
        token = sessions.create()
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response

    @app.post("/logout")
    async def logout(request: Request):
        sessions.revoke(request.cookies.get(SESSION_COOKIE))
        response = RedirectResponse(
            url="/login" if auth_enabled() else "/", status_code=303
        )
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(
            content=render_dashboard(config, show_logout=auth_enabled())
        )

    @app.get("/api/status")
    async def status() -> JSONResponse:
        results, ts = _current_status()
        # HTTP 200 even when routers are unreachable; per-router status carries it.
        return JSONResponse(status_code=200, content=_status_payload(results, ts))

    @app.get("/api/history")
    async def history(hours: int = 24) -> JSONResponse:
        hours = max(1, min(hours, 24 * 30))
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        series = load_history(
            config.metrics_db, [router.name for router in config.routers], since
        )
        return JSONResponse(
            status_code=200,
            content={
                "generated_at": generated_at(),
                "hours": hours,
                "series": series,
            },
        )

    @app.post("/api/backups")
    async def backups() -> JSONResponse:
        results = _backup_results(config)
        ts = generated_at()
        record_snapshot(config.metrics_db, ts, results)
        return JSONResponse(status_code=200, content=_run_payload(results, ts))

    # Legacy endpoint kept for existing clients.
    @app.post("/backups")
    async def backups_legacy() -> JSONResponse:
        results = _backup_results(config)
        ts = generated_at()
        record_snapshot(config.metrics_db, ts, results)
        return JSONResponse(status_code=200, content=_run_payload(results, ts))

    @app.post("/api/backups/{name}")
    async def backup_one(name: str) -> JSONResponse:
        try:
            scoped = filter_config(config, [name])
        except RouterSelectionError as exc:
            return JSONResponse(status_code=404, content={"detail": str(exc)})
        results = _backup_results(scoped)
        ts = generated_at()
        record_snapshot(config.metrics_db, ts, results)
        return JSONResponse(status_code=200, content=_run_payload(results, ts))

    return app
