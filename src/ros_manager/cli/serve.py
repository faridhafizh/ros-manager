"""``rosm serve``: run the FastAPI backup server with Uvicorn."""

from __future__ import annotations

import typer

from ..api import create_app
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
    import uvicorn

    app_api = create_app(config)
    uvicorn.run(app_api, host=host, port=port)
