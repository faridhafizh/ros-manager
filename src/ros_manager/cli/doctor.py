"""``rosm doctor``: extended diagnostics for every router."""

from __future__ import annotations

import typer

from ..service import run_doctor_inventory
from .app import app
from .common import (
    NO_VALUE,
    handle_doctor_results,
    load_app_config,
    resolve_format,
    select_config,
)


@app.command()
def doctor(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    format: str = typer.Option("text", "--format", help="Output format: text, json, csv."),
    output: str = typer.Option(NO_VALUE, "--output", help="Write output to file instead of terminal."),
    router: str = typer.Option(NO_VALUE, "--router", help="Comma-separated router names to include."),
    group: str = typer.Option(NO_VALUE, "--group", help="Comma-separated router groups to include."),
) -> None:
    """Report RouterOS version, board, disk, sensors, and API latency."""
    cfg = select_config(load_app_config(config), router, group)
    fmt = resolve_format(format)
    results = run_doctor_inventory(cfg)
    raise typer.Exit(handle_doctor_results(results, fmt, output))
