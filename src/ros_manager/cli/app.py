"""The shared Typer application instance."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="rosm",
    help="ROS Manager: RouterOS fleet health checks, backups, diff, and scheduler.",
    no_args_is_help=True,
)
