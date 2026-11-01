"""``rosm check``: health check every router in the inventory."""

from __future__ import annotations

import typer

from ..service import run_inventory
from .app import app
from .common import (
    NO_VALUE,
    REPORT_FORMATS,
    handle_results,
    load_app_config,
    resolve_format,
    select_config,
)


@app.command()
def check(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    format: str = typer.Option("text", "--format", help="Output format: text, json, csv, html."),
    output: str = typer.Option(NO_VALUE, "--output", help="Write output to file instead of terminal."),
    router: str = typer.Option(NO_VALUE, "--router", help="Comma-separated router names to include."),
    group: str = typer.Option(NO_VALUE, "--group", help="Comma-separated router groups to include."),
) -> None:
    """Health check every router in the inventory."""
    cfg = select_config(load_app_config(config), router, group)
    fmt = resolve_format(format, REPORT_FORMATS)
    results = run_inventory(cfg, do_check=True, do_backup=False)
    raise typer.Exit(handle_results(results, fmt, output, include_backup=False))
