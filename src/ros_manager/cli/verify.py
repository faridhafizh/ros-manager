"""``rosm verify``: validate a local backup file."""

from __future__ import annotations

from typing import Optional

import typer

from ..restore import verify_backup_file
from .app import app


@app.command()
def verify(
    file: str = typer.Argument(..., help="Path to the backup .rsc file to verify."),
    max_age_days: Optional[int] = typer.Option(
        None, "--max-age-days", help="Fail if the backup is older than this many days."
    ),
) -> None:
    """Check that a backup file is readable, non-empty, and looks like RouterOS."""
    try:
        problems = verify_backup_file(file, max_age_days)
    except UnicodeDecodeError as exc:
        typer.secho(
            f"error reading backup file: not valid UTF-8 ({exc})",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2) from exc
    except OSError as exc:
        typer.secho(f"error reading backup file: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    if problems:
        for problem in problems:
            typer.secho(f"{file}: {problem}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(f"{file}: ok")
    raise typer.Exit(0)
