"""Self-contained HTML reports and the web dashboard shell.

Everything is inline (CSS/JS only), so a generated report can be opened
offline or shared without external assets.
"""

from __future__ import annotations

import html
from typing import Optional

from .config import AppConfig
from .serialize import generated_at, health_entry, interfaces_up_total, run_entry
from .service import RouterResult

_STYLE = """
:root { color-scheme: light dark; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
       margin: 2rem; line-height: 1.4; }
h1 { margin-bottom: .25rem; }
.meta { color: #6b7280; margin-bottom: 1.5rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #d1d5db; padding: .5rem .6rem;
         text-align: left; vertical-align: top; }
th { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em;
     color: #6b7280; }
small { color: #6b7280; }
.badge { display: inline-block; padding: .1rem .5rem; border-radius: 999px;
         font-size: .8rem; font-weight: 600; }
.badge.ok { background: #dcfce7; color: #166534; }
.badge.error { background: #fee2e2; color: #991b1b; }
.badge.unknown { background: #e5e7eb; color: #374151; }
.error { color: #991b1b; }
button { padding: .35rem .7rem; border-radius: .4rem; border: 1px solid #9ca3af;
         background: transparent; cursor: pointer; }
button:disabled { opacity: .5; cursor: default; }
"""


def _escape(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _badge(status: Optional[str]) -> str:
    status = status or "unknown"
    css = status if status in {"ok", "error"} else "unknown"
    return f'<span class="badge {css}">{_escape(status)}</span>'


def _format_bytes(value: Optional[int]) -> str:
    if value is None:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def render_html_report(
    results: list[RouterResult],
    include_backup: bool = False,
    title: str = "ROS Manager report",
) -> str:
    """Render a standalone HTML table for check/run results."""
    header = [
        "Router", "Status", "Temp", "CPU", "Memory", "Interfaces", "Error",
    ]
    if include_backup:
        header += ["Backup", "Pruned", "Backup path"]

    rows: list[str] = []
    for result in results:
        entry = run_entry(result) if include_backup else health_entry(result)
        up, total = interfaces_up_total(result.health)
        memory = "—"
        if entry["memory_free_bytes"] is not None and entry["memory_total_bytes"] is not None:
            memory = (
                f"{_format_bytes(entry['memory_free_bytes'])} / "
                f"{_format_bytes(entry['memory_total_bytes'])}"
            )
        cells = [
            f"<td><strong>{_escape(entry['name'])}</strong><br>"
            f"<small>{_escape(entry['host'])}</small></td>",
            f"<td>{_badge(entry['status'])}</td>",
            f"<td>{_escape(entry['temperature_c'])}</td>",
            f"<td>{_escape(entry['cpu_load_percent'])}</td>",
            f"<td>{memory}</td>",
            f"<td>{'—' if total is None else f'{up}/{total}'}</td>",
            f'<td class="error">{_escape(entry["error"])}</td>',
        ]
        if include_backup:
            backup = entry.get("backup", {})
            cells += [
                f"<td>{_badge(backup.get('status'))}</td>",
                f"<td>{_escape(backup.get('pruned'))}</td>",
                f"<td>{_escape(backup.get('path'))}</td>",
            ]
        rows.append("<tr>" + "".join(cells) + "</tr>")

    header_html = "".join(f"<th>{_escape(col)}</th>" for col in header)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<h1>{_escape(title)}</h1>
<p class="meta">Generated at {_escape(generated_at())} · {len(results)} router(s)</p>
<table>
<thead><tr>{header_html}</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</body>
</html>
"""


def render_dashboard(config: AppConfig) -> str:
    """Render the dashboard shell; status is filled in by ``/api/status``."""
    rows = "\n".join(
        f"""<tr data-router="{_escape(router.name)}">
<td><strong>{_escape(router.name)}</strong><br><small>{_escape(router.host)}</small></td>
<td class="status">{_badge("unknown")}</td>
<td class="temp">—</td>
<td class="cpu">—</td>
<td class="mem">—</td>
<td class="ifaces">—</td>
<td class="error"></td>
<td><button class="backup" data-router="{_escape(router.name)}">Back up</button></td>
</tr>"""
        for router in config.routers
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROS Manager dashboard</title>
<style>{_STYLE}</style>
</head>
<body>
<h1>ROS Manager</h1>
<p class="meta">{len(config.routers)} router(s) · <span id="updated">loading…</span></p>
<p><button id="backup-all">Back up all</button></p>
<table>
<thead><tr>
<th>Router</th><th>Status</th><th>Temp</th><th>CPU</th><th>Memory</th>
<th>Interfaces</th><th>Error</th><th></th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
<script>
function fmt(value, suffix) {{
  return (value === null || value === undefined) ? '—' : value + suffix;
}}
function setStatus(tr, r) {{
  const status = tr.querySelector('.status');
  const badge = status.querySelector('.badge');
  if (badge) {{
    badge.textContent = r.status;
    badge.className = 'badge ' + (r.status === 'ok' ? 'ok' : 'error');
  }} else {{
    status.textContent = r.status;
  }}
  tr.querySelector('.temp').textContent = fmt(r.temperature_c, ' °C');
  tr.querySelector('.cpu').textContent = fmt(r.cpu_load_percent, ' %');
  if (r.memory_free_bytes !== null && r.memory_total_bytes !== null) {{
    const mb = v => Math.round(v / 1048576);
    tr.querySelector('.mem').textContent =
      mb(r.memory_free_bytes) + ' / ' + mb(r.memory_total_bytes) + ' MB';
  }} else {{
    tr.querySelector('.mem').textContent = '—';
  }}
  const ifaces = Array.isArray(r.interfaces) ? r.interfaces : [];
  const up = ifaces.filter(i => i.running === true).length;
  tr.querySelector('.ifaces').textContent =
    ifaces.length ? up + ' / ' + ifaces.length : '—';
  tr.querySelector('.error').textContent = r.error || '';
}}
async function refresh() {{
  const updated = document.getElementById('updated');
  try {{
    const res = await fetch('api/status');
    if (!res.ok) {{ updated.textContent = 'status error'; return; }}
    const data = await res.json();
    const byName = Object.fromEntries(data.routers.map(r => [r.name, r]));
    document.querySelectorAll('tr[data-router]').forEach(tr => {{
      const r = byName[tr.dataset.router];
      if (r) setStatus(tr, r);
    }});
    updated.textContent = 'updated ' + data.generated_at;
  }} catch (err) {{
    updated.textContent = 'status error';
  }}
}}
async function post(url) {{
  try {{ await fetch(url, {{ method: 'POST' }}); }} finally {{ refresh(); }}
}}
document.getElementById('backup-all').addEventListener('click', event => {{
  event.target.disabled = true;
  post('api/backups').finally(() => {{ event.target.disabled = false; }});
}});
document.querySelectorAll('button.backup').forEach(btn => {{
  btn.addEventListener('click', () => {{
    btn.disabled = true;
    post('api/backups/' + encodeURIComponent(btn.dataset.router))
      .finally(() => {{ btn.disabled = false; }});
  }});
}});
refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>
"""


def render_error_page(message: str) -> str:
    """Safe HTML page shown when the inventory cannot be loaded."""
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>ROS Manager error</title>
<style>{_STYLE}</style></head>
<body>
<h1>ROS Manager</h1>
<p class="error">{_escape(message)}</p>
</body>
</html>
"""
