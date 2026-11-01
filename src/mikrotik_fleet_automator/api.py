"""FastAPI application for triggering backups over HTTP."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import ConfigError, load_config
from .service import RouterResult, run_inventory


def _entry(result: RouterResult) -> dict[str, Any]:
    backup = result.backup
    return {
        "name": result.name,
        "host": result.host,
        "backup": {
            "status": backup.status if backup else "skipped",
            "error": backup.error if backup else None,
            "path": backup.path if backup else None,
        },
        "check": {
            "status": result.health.status if result.health else "error",
            "error": result.health.error if result.health else "check not performed",
        },
    }


def create_app(config_path: str | Path) -> FastAPI:
    """Create a FastAPI app that runs backups via the shared service.

    Configuration load/validation failures yield HTTP 500 with a safe message
    (no secrets or tokens in the response).
    """
    app = FastAPI(title="MikroTik Fleet Automator")

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        # Config is fixed at startup; every request reports the same safe error.
        message = str(exc)
        @app.post("/backups")
        async def _config_failed() -> JSONResponse:  # type: ignore[no-redef]
            return JSONResponse(
                status_code=500,
                content={"detail": f"config error: {message}"},
            )
        return app

    @app.post("/backups")
    async def backups() -> JSONResponse:
        results: list[RouterResult] = run_inventory(
            config, do_check=False, do_backup=True
        )
        payload = {
            "generated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "routers": [_entry(r) for r in results],
        }
        # HTTP 200 even when some routers fail; per-router status carries it.
        return JSONResponse(status_code=200, content=payload)

    return app
