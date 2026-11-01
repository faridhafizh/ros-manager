"""Typer CLI package for ROS Manager.

Importing this package registers every sub-command on the shared ``app``
instance defined in :mod:`ros_manager.cli.app`.
"""

from __future__ import annotations

from .app import app
from . import (  # noqa: F401,E402
    backup,
    check,
    diff,
    doctor,
    history,
    restore,
    run,
    schedule,
    serve,
    verify,
)

__all__ = ["app"]
