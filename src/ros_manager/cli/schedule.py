"""``rosm schedule``: run immediately, then repeat on an interval."""

from __future__ import annotations

import threading

import typer

from ..scheduler import run_schedule
from .app import app
from .common import NO_VALUE, load_app_config, select_config


@app.command()
def schedule(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    interval_seconds: int = typer.Option(..., "--interval-seconds", help="Interval between runs in seconds."),
    router: str = typer.Option(NO_VALUE, "--router", help="Comma-separated router names to include."),
    group: str = typer.Option(NO_VALUE, "--group", help="Comma-separated router groups to include."),
) -> None:
    """Run `run` immediately, then repeat every interval until stopped."""
    cfg = select_config(load_app_config(config), router, group)
    if interval_seconds <= 0:
        typer.secho("interval_seconds must be positive", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    stop_event = threading.Event()
    try:
        run_schedule(cfg, interval_seconds, stop_event=stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    raise typer.Exit(0)
