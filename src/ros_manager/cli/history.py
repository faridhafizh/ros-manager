"""``rosm history``: list stored backups and diff the two newest."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import typer

from ..storage import list_backups
from .app import app
from .common import NO_VALUE, load_app_config


@app.command()
def history(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    router: str = typer.Option(..., "--router", help="Router whose backups to list."),
    diff: bool = typer.Option(
        False, "--diff", help="Diff the two newest backups instead of listing them."
    ),
) -> None:
    """List backups for a router, or diff its two newest backups."""
    cfg = load_app_config(config)
    if not any(r.name == router for r in cfg.routers):
        typer.secho(f"router selection error: unknown router: {router!r}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)

    backups = list_backups(cfg.backup_dir, router)
    if not backups:
        typer.secho(
            f"no backups found for {router!r} in {cfg.backup_dir}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if diff:
        if len(backups) < 2:
            typer.secho(
                "need at least two backups to diff", err=True, fg=typer.colors.RED
            )
            raise typer.Exit(2)
        old, new = backups[-2], backups[-1]
        old_lines = Path(old).read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = Path(new).read_text(encoding="utf-8").splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(old_lines, new_lines, fromfile=str(old), tofile=str(new))
        )
        if diff_lines:
            sys.stdout.write("".join(diff_lines))
            raise typer.Exit(1)
        raise typer.Exit(0)

    typer.echo(f"{router} backups in {cfg.backup_dir} ({len(backups)})")
    for path in reversed(backups):
        typer.echo(f"  {path.name}  {path.stat().st_size}B  {path}")
    raise typer.Exit(0)
