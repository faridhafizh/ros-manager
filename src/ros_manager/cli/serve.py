"""``rosm serve``: run the FastAPI backup server with Uvicorn."""

from __future__ import annotations

import typer

from ..api import create_app
from ..auth import ENV_PASSWORD, auth_enabled
from .app import app
from .common import NO_VALUE, load_app_config


@app.command()
def serve(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address."),
    port: int = typer.Option(8000, "--port", help="Port to listen on."),
) -> None:
    """Run the FastAPI backup server with Uvicorn."""
    load_app_config(config)  # validate early with a friendly message
    if not auth_enabled():
        typer.secho(
            "dashboard is open without a login; set "
            f"{ENV_PASSWORD} to require one",
            fg=typer.colors.YELLOW,
        )
    import uvicorn

    app_api = create_app(config)
    uvicorn.run(app_api, host=host, port=port)
