"""Lightweight single-password login for the web dashboard.

The dashboard is open by default. Setting ``ROSM_DASH_PASSWORD`` turns on a
simple login form; sessions live in memory and expire after 12 hours. This is
deliberately minimal (one shared team password, no user database) while the
checks stay in one place so role-based access can be layered on later.
"""

from __future__ import annotations

import hmac
import os
import secrets
import threading
import time
from typing import Optional

ENV_PASSWORD = "ROSM_DASH_PASSWORD"
SESSION_COOKIE = "rosm_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


def dashboard_password() -> Optional[str]:
    """Return the configured dashboard password, or ``None`` when disabled."""
    value = os.environ.get(ENV_PASSWORD, "")
    if not value.strip():
        return None
    return value


def auth_enabled() -> bool:
    """True when a dashboard password is configured via the environment."""
    return dashboard_password() is not None


def check_password(candidate: str) -> bool:
    """Constant-time comparison against the configured password."""
    expected = dashboard_password()
    if expected is None:
        return False
    return hmac.compare_digest(candidate, expected)


class SessionStore:
    """In-memory session tokens with a fixed lifetime."""

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._sessions: dict[str, float] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = time.monotonic() + self._ttl
        return token

    def is_valid(self, token: Optional[str]) -> bool:
        if not token:
            return False
        now = time.monotonic()
        with self._lock:
            expiry = self._sessions.get(token)
            if expiry is None:
                return False
            if expiry <= now:
                self._sessions.pop(token, None)
                return False
            return True

    def revoke(self, token: Optional[str]) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)
