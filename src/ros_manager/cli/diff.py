"""``rosm diff``: unified diff between two backup files."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

import typer

from .app import app


@app.command()
def diff(
    old: str = typer.Argument(..., help="Path to old backup .rsc file."),
    new: str = typer.Argument(..., help="Path to new backup .rsc file."),
) -> None:
    """Print unified diff between two backup files; exit 0 if same, 1 if different."""
    try:
        old_lines = Path(old).read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = Path(new).read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        typer.secho(f"error reading backup file: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc
    diff_lines = list(
        difflib.unified_diff(old_lines, new_lines, fromfile=old, tofile=new)
    )
    if diff_lines:
        sys.stdout.write("".join(diff_lines))
        raise typer.Exit(1)
    raise typer.Exit(0)
