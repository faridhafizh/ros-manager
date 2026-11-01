"""``rosm backup``: back up configuration of every router."""

from __future__ import annotations

import typer

from ..service import any_failure, run_inventory
from .app import app
from .common import NO_VALUE, format_text, load_app_config, select_config


@app.command()
def backup(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    router: str = typer.Option(NO_VALUE, "--router", help="Comma-separated router names to include."),
    group: str = typer.Option(NO_VALUE, "--group", help="Comma-separated router groups to include."),
) -> None:
    """Back up configuration of every router."""
    cfg = select_config(load_app_config(config), router, group)
    results = run_inventory(cfg, do_check=False, do_backup=True)
    typer.echo(format_text(results, include_backup=True))
    raise typer.Exit(1 if any_failure(results) else 0)
