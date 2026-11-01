"""``rosm restore``: dry-run by default, upload + import with ``--apply``."""

from __future__ import annotations

import typer

from ..restore import RestoreError, RestorePlan, apply_restore, plan_restore
from .app import app
from .common import NO_VALUE, load_app_config

_DIFF_LIMIT = 200


def format_restore_plan(plan: RestorePlan) -> str:
    lines = [
        f"Restore plan for {plan.router.name} ({plan.router.host})",
        f"  file: {plan.file} ({plan.size} bytes)",
        f"  latest backup: {plan.latest if plan.latest else '(none)'}",
        "  preview:",
    ]
    lines.extend(f"    {line}" for line in plan.preview)
    lines.append("  diff (latest -> file):")
    if plan.diff:
        diff_lines = plan.diff.splitlines()
        lines.extend(f"    {line}" for line in diff_lines[:_DIFF_LIMIT])
        if len(diff_lines) > _DIFF_LIMIT:
            lines.append(f"    ... ({len(diff_lines) - _DIFF_LIMIT} more lines)")
    else:
        lines.append("    (no differences or no previous backup)")
    return "\n".join(lines)


@app.command()
def restore(
    config: str = typer.Option(NO_VALUE, "--config", help="Path to inventory YAML."),
    router: str = typer.Option(..., "--router", help="Name of the router to restore."),
    file: str = typer.Option(..., "--file", help="Path to the backup .rsc file."),
    apply: bool = typer.Option(
        False, "--apply", help="Actually upload and /import the file (default: dry-run)."
    ),
) -> None:
    """Show what a restore would change; use --apply to upload and import."""
    cfg = load_app_config(config)
    try:
        plan = plan_restore(cfg, router, file)
    except RestoreError as exc:
        typer.secho(f"restore error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc
    except (OSError, UnicodeDecodeError) as exc:
        typer.secho(f"error reading backup file: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from exc

    typer.echo(format_restore_plan(plan))

    if not apply:
        typer.secho(
            "dry-run: re-run with --apply to upload and /import this file",
            err=True,
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(0)

    try:
        remote_name = apply_restore(plan.router, plan.file)
    except RestoreError as exc:
        typer.secho(f"restore error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    typer.echo(
        f"uploaded {remote_name} and ran /import on {plan.router.name}; "
        "no reboot was performed"
    )
    raise typer.Exit(0)
