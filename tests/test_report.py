"""HTML report and dashboard rendering tests."""

from __future__ import annotations

from ros_manager.models import AppConfig, RouterConfig, RouterHealth
from ros_manager.report import (
    render_dashboard,
    render_error_page,
    render_html_report,
)
from ros_manager.service import BackupResult, RouterResult


def _health(name="r1", host="10.0.0.1", **kwargs):
    return RouterHealth(name=name, host=host, status="ok", **kwargs)


def test_report_contains_router_rows_and_meta():
    results = [
        RouterResult(name="r1", host="10.0.0.1", health=_health(temperature_c=41)),
        RouterResult(
            name="r2",
            host="10.0.0.2",
            health=RouterHealth(name="r2", host="10.0.0.2", status="error", error="timeout"),
        ),
    ]
    html = render_html_report(results)
    assert "<!doctype html>" in html
    assert "r1" in html and "r2" in html
    assert "timeout" in html
    assert "2 router(s)" in html
    # Standalone: no external assets.
    assert "http://" not in html and "https://" not in html


def test_report_escapes_untrusted_values():
    results = [
        RouterResult(
            name="<script>alert(1)</script>",
            host="10.0.0.1",
            health=RouterHealth(
                name="<script>alert(1)</script>",
                host="10.0.0.1",
                status="error",
                error="<img src=x onerror=alert(2)>",
            ),
        )
    ]
    html = render_html_report(results)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html
    assert "&lt;img" in html


def test_report_with_backup_columns():
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=_health(),
            backup=BackupResult(
                name="r1", host="10.0.0.1", status="ok", path="/b/r1.rsc", pruned=2
            ),
        )
    ]
    html = render_html_report(results, include_backup=True, title="Run report")
    assert "Run report" in html
    assert "Backup path" in html
    assert "/b/r1.rsc" in html
    assert ">2<" in html


def test_report_handles_missing_check():
    results = [RouterResult(name="r1", host="10.0.0.1")]
    html = render_html_report(results)
    assert "check not performed" in html


def test_report_formats_memory_bytes():
    results = [
        RouterResult(
            name="r1",
            host="10.0.0.1",
            health=_health(memory_total_bytes=1024 * 1024 * 512, memory_free_bytes=1024 * 1024 * 256),
        )
    ]
    html = render_html_report(results)
    assert "256.0 MB" in html
    assert "512.0 MB" in html


def test_dashboard_lists_routers_and_escapes_names():
    config = AppConfig(
        backup_dir="backups",
        routers=[
            RouterConfig(name="core-1", host="10.0.0.1", username="a", password_env="P"),
            RouterConfig(
                name='<b>"edge"</b>',
                host="10.0.0.2",
                username="a",
                password_env="P",
            ),
        ],
    )
    html = render_dashboard(config)
    assert "core-1" in html
    assert 'data-router="core-1"' in html
    assert "<b>\"edge\"</b>" not in html
    assert "&lt;b&gt;" in html
    assert "api/status" in html
    assert "api/backups" in html
    assert "2 router(s)" in html


def test_error_page_escapes_message():
    html = render_error_page("config error: <bad>")
    assert "&lt;bad&gt;" in html
    assert "<bad>" not in html
