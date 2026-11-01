"""``rosm run``: check and back up every router, then summarize both."""

from __future__ import annotations

import typer

from ..notify import send_notifications
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
def run(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    format: str = typer.Option("text", "--format", help="Output format: text, json, csv, html."),
    output: str = typer.Option(NO_VALUE, "--output", help="Write output to file instead of terminal."),
    notify: bool = typer.Option(False, "--notify", help="Notify on router status changes."),
    notify_all: bool = typer.Option(
        False, "--notify-all", help="Send a full summary even without status changes."
    ),
    router: str = typer.Option(NO_VALUE, "--router", help="Comma-separated router names to include."),
    group: str = typer.Option(NO_VALUE, "--group", help="Comma-separated router groups to include."),
) -> None:
    """Check and back up every router, then summarize both."""
    cfg = select_config(load_app_config(config), router, group)
    fmt = resolve_format(format, REPORT_FORMATS)
    results = run_inventory(cfg, do_check=True, do_backup=True)
    exit_code = handle_results(results, fmt, output, include_backup=True)
    if notify or notify_all:
        try:
            outcome = send_notifications(cfg, results, notify_all=notify_all)
        except Exception as exc:  # noqa: BLE001 - surface as CLI error
            typer.secho(f"notification error: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1) from exc
        if not outcome.sent and outcome.skipped_reason:
            typer.secho(
                f"notification skipped: {outcome.skipped_reason}",
                err=True,
                fg=typer.colors.YELLOW,
            )
    raise typer.Exit(exit_code)
