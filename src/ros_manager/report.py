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
:root { color-scheme: light dark; --ok: #16a34a; --warn: #d97706;
        --error: #dc2626; --muted: #6b7280; --line: #d1d5db; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
       margin: 2rem auto; max-width: 1200px; padding: 0 1rem; line-height: 1.45; }
h1 { margin-bottom: .25rem; }
h2 { font-size: 1rem; margin: 0 0 .25rem; }
.meta { color: var(--muted); margin-bottom: 1rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid var(--line); padding: .5rem .6rem;
         text-align: left; vertical-align: top; }
th { font-size: .8rem; text-transform: uppercase; letter-spacing: .04em;
     color: var(--muted); }
small { color: var(--muted); }
.badge { display: inline-block; padding: .1rem .5rem; border-radius: 999px;
         font-size: .8rem; font-weight: 600; }
.badge.ok { background: #dcfce7; color: #166534; }
.badge.warn { background: #fef3c7; color: #92400e; }
.badge.error { background: #fee2e2; color: #991b1b; }
.badge.unknown { background: #e5e7eb; color: #374151; }
.error { color: #991b1b; }
button { padding: .35rem .7rem; border-radius: .4rem; border: 1px solid #9ca3af;
         background: transparent; cursor: pointer; }
button:disabled { opacity: .5; cursor: default; }
.topbar { display: flex; justify-content: space-between; align-items: flex-start;
          gap: 1rem; flex-wrap: wrap; }
.actions { display: flex; gap: .5rem; align-items: center; }
.attention { border-radius: .6rem; padding: .7rem 1rem; margin: 1rem 0;
             border: 1px solid var(--line); }
.attention.ok { background: #f0fdf4; border-color: #86efac; }
.attention.warn { background: #fffbeb; border-color: #fcd34d; }
.attention.error { background: #fef2f2; border-color: #fca5a5; }
.attention ul { margin: .35rem 0 0; padding-left: 1.2rem; }
.attention li.warn { color: #92400e; }
.attention li.error { color: #991b1b; }
.cards { display: grid; gap: 1rem; margin: 1rem 0 1.5rem;
         grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.card { border: 1px solid var(--line); border-left: 6px solid var(--muted);
        border-radius: .6rem; padding: .9rem 1rem; }
.card[data-state="ok"] { border-left-color: var(--ok); }
.card[data-state="warn"] { border-left-color: var(--warn); }
.card[data-state="error"] { border-left-color: var(--error); }
.card-head { display: flex; justify-content: space-between; gap: .5rem;
             align-items: flex-start; }
.metrics { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem .9rem;
           margin: .75rem 0 .25rem; }
.metric { display: flex; flex-direction: column; }
.metric .label { font-size: .72rem; text-transform: uppercase;
                 letter-spacing: .04em; color: var(--muted); }
.metric .value { font-weight: 700; font-size: 1.05rem; }
.metric .note { font-size: .75rem; color: var(--muted); }
.spark { width: 100%; height: 34px; margin: .4rem 0 .2rem; display: block; }
.spark polyline { fill: none; stroke-width: 1.6; vector-effect: non-scaling-stroke; }
.spark .cpu { stroke: #2563eb; }
.spark .mem { stroke: #7c3aed; stroke-dasharray: 3 3; }
.card-actions { display: flex; gap: .5rem; align-items: center; }
.legend { margin: .5rem 0 1.5rem; }
.detail { margin-top: 1rem; }
.login { max-width: 360px; margin: 4rem auto; }
.login input { width: 100%; box-sizing: border-box; padding: .45rem .6rem;
               margin: .5rem 0 .8rem; border: 1px solid var(--line);
               border-radius: .4rem; }
@media (prefers-color-scheme: dark) {
  .attention.ok { background: #052e16; border-color: #166534; }
  .attention.warn { background: #451a03; border-color: #92400e; }
  .attention.error { background: #450a0a; border-color: #991b1b; }
  .attention li.warn { color: #fbbf24; }
  .attention li.error { color: #fca5a5; }
}
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


_DASHBOARD_JS = """
const THRESHOLDS = {
  cpuWarn: 80, cpuHigh: 90,
  memLowPct: 15, memCriticalPct: 10,
  tempWarn: 70, tempHot: 80,
};

function fmt(value, suffix) {
  return (value === null || value === undefined) ? '—' : value + suffix;
}

function fmtBytes(bytes) {
  if (bytes === null || bytes === undefined) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes, index = 0;
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1; }
  return (index === 0 ? Math.round(size) : size.toFixed(1)) + ' ' + units[index];
}

function cpuNote(value) {
  if (value === null || value === undefined) return '';
  if (value >= THRESHOLDS.cpuHigh) return 'very high — almost no CPU headroom left';
  if (value >= THRESHOLDS.cpuWarn) return 'high — move heavy rules to another router';
  if (value >= 50) return 'moderate — normal under load';
  return 'light — plenty of headroom';
}

function memNote(free, total) {
  if (free === null || free === undefined || !total) return '';
  const pct = free / total * 100;
  if (pct < THRESHOLDS.memCriticalPct) return 'critical — almost no free memory';
  if (pct < THRESHOLDS.memLowPct) return 'low — free memory is running out';
  if (pct < 30) return 'getting tight';
  return 'healthy';
}

function tempNote(value) {
  if (value === null || value === undefined) return 'no temperature sensor on this model';
  if (value >= THRESHOLDS.tempHot) return 'very hot — check cooling immediately';
  if (value >= THRESHOLDS.tempWarn) return 'hot — check room ventilation';
  if (value >= 55) return 'warm but normal';
  return 'cool';
}

function downInterfaces(router) {
  const ifaces = Array.isArray(router.interfaces) ? router.interfaces : [];
  return ifaces.filter(i => i.running !== true && i.disabled !== true);
}

function stateFor(router) {
  if (router.status !== 'ok') return 'error';
  const total = router.memory_total_bytes;
  const memPct = (router.memory_free_bytes !== null
    && router.memory_free_bytes !== undefined && total)
    ? router.memory_free_bytes / total * 100 : null;
  if ((router.cpu_load_percent !== null
        && router.cpu_load_percent >= THRESHOLDS.cpuWarn)
      || (memPct !== null && memPct < THRESHOLDS.memLowPct)
      || (router.temperature_c !== null
        && router.temperature_c >= THRESHOLDS.tempWarn)
      || downInterfaces(router).length > 0) {
    return 'warn';
  }
  return 'ok';
}

function applyCard(card, router) {
  const state = stateFor(router);
  card.dataset.state = state;
  const badge = card.querySelector('.status');
  const label = state === 'error' ? 'error' : (state === 'warn' ? 'warning' : 'ok');
  badge.textContent = label;
  badge.className = 'badge ' + (state === 'error' ? 'error' : (state === 'warn' ? 'warn' : 'ok'));

  card.querySelector('.temp').textContent = fmt(router.temperature_c, ' °C');
  card.querySelector('.temp-note').textContent = tempNote(router.temperature_c);
  card.querySelector('.cpu').textContent = fmt(router.cpu_load_percent, ' %');
  card.querySelector('.cpu-note').textContent = cpuNote(router.cpu_load_percent);
  if (router.memory_free_bytes !== null && router.memory_free_bytes !== undefined) {
    card.querySelector('.mem').textContent = fmtBytes(router.memory_free_bytes) + ' free';
    card.querySelector('.mem-note').textContent =
      memNote(router.memory_free_bytes, router.memory_total_bytes);
  } else {
    card.querySelector('.mem').textContent = '—';
    card.querySelector('.mem-note').textContent = '';
  }

  const ifaces = Array.isArray(router.interfaces) ? router.interfaces : [];
  const up = ifaces.filter(i => i.running === true).length;
  card.querySelector('.ifaces').textContent =
    ifaces.length ? up + ' / ' + ifaces.length : '—';
  const down = downInterfaces(router);
  card.querySelector('.ifaces-note').textContent = down.length
    ? down.length + ' down: ' + down.map(i => i.name).join(', ')
    : (ifaces.length ? 'all enabled interfaces are up' : '');
  card.querySelector('.error').textContent = router.error || '';
}

function recommendations(routers) {
  const items = [];
  routers.forEach(router => {
    if (router.status !== 'ok') {
      items.push({
        level: 'error',
        text: router.name + ' is not responding — check power and network, then ask a senior to review the configuration.'
          + (router.error ? ' (' + router.error + ')' : ''),
      });
      return;
    }
    if (router.cpu_load_percent !== null
        && router.cpu_load_percent >= THRESHOLDS.cpuWarn) {
      items.push({
        level: 'warn',
        text: router.name + ' CPU is at ' + router.cpu_load_percent
          + '% — move heavy firewall rules or queues to another router.',
      });
    }
    const total = router.memory_total_bytes;
    if (router.memory_free_bytes !== null && total) {
      const pct = router.memory_free_bytes / total * 100;
      if (pct < THRESHOLDS.memLowPct) {
        items.push({
          level: 'warn',
          text: router.name + ' has only ' + pct.toFixed(0)
            + '% free memory — check for runaway processes or plan a device upgrade.',
        });
      }
    }
    if (router.temperature_c !== null
        && router.temperature_c >= THRESHOLDS.tempWarn) {
      items.push({
        level: 'warn',
        text: router.name + ' is running at ' + router.temperature_c
          + '°C — check room ventilation and airflow.',
      });
    }
    downInterfaces(router).forEach(iface => {
      items.push({
        level: 'warn',
        text: router.name + ': interface ' + iface.name
          + ' is down — check the cable or the peer device.',
      });
    });
  });
  return items;
}

function renderAttention(items) {
  const panel = document.getElementById('attention');
  const list = document.getElementById('attention-list');
  list.replaceChildren();
  if (!items.length) {
    panel.className = 'attention ok';
    const li = document.createElement('li');
    li.textContent = 'All routers are healthy.';
    list.appendChild(li);
    return;
  }
  panel.className = 'attention ' + (items.some(i => i.level === 'error') ? 'error' : 'warn');
  items.forEach(item => {
    const li = document.createElement('li');
    li.className = item.level;
    li.textContent = item.text;
    list.appendChild(li);
  });
}

function polyline(values, maxValue) {
  const present = values.filter(v => v !== null && v !== undefined);
  if (present.length < 2) return '';
  const max = maxValue || Math.max(...present, 1);
  const step = values.length > 1 ? 100 / (values.length - 1) : 0;
  return values.map((value, index) => {
    if (value === null || value === undefined) return null;
    const y = 26 - (Math.min(value, max) / max) * 24;
    return (index * step).toFixed(2) + ',' + y.toFixed(2);
  }).filter(point => point !== null).join(' ');
}

function drawSpark(card, points) {
  const svg = card.querySelector('.spark');
  if (!svg) return;
  const memMax = Math.max(...points.map(p => p.mem_total || 0), 1);
  svg.querySelector('.cpu').setAttribute(
    'points', polyline(points.map(p => p.cpu), 100));
  svg.querySelector('.mem').setAttribute(
    'points', polyline(points.map(p => p.mem_free), memMax));
}

async function refreshHistory() {
  try {
    const res = await fetch('api/history?hours=24');
    if (!res.ok) return;
    const data = await res.json();
    const series = data.series || {};
    document.querySelectorAll('article.card[data-router]').forEach(card => {
      drawSpark(card, series[card.dataset.router] || []);
    });
  } catch (err) {
    /* trends are best-effort */
  }
}

async function refresh() {
  const updated = document.getElementById('updated');
  try {
    const res = await fetch('api/status');
    if (res.status === 401) { window.location.href = 'login'; return; }
    if (!res.ok) { updated.textContent = 'status error'; return; }
    const data = await res.json();
    const byName = Object.fromEntries(data.routers.map(r => [r.name, r]));
    const seen = [];
    document.querySelectorAll('article.card[data-router]').forEach(card => {
      const router = byName[card.dataset.router];
      if (!router) return;
      applyCard(card, router);
      seen.push(router);
    });
    document.querySelectorAll('tr[data-detail-router]').forEach(row => {
      const router = byName[row.dataset.detailRouter];
      if (!router) return;
      const ifaces = Array.isArray(router.interfaces) ? router.interfaces : [];
      const up = ifaces.filter(i => i.running === true).length;
      const down = downInterfaces(router);
      row.querySelector('.d-status').textContent = router.status;
      row.querySelector('.d-temp').textContent = fmt(router.temperature_c, ' °C');
      row.querySelector('.d-cpu').textContent = fmt(router.cpu_load_percent, ' %');
      row.querySelector('.d-mem').textContent =
        (router.memory_free_bytes !== null && router.memory_total_bytes !== null)
          ? fmtBytes(router.memory_free_bytes) + ' / '
            + fmtBytes(router.memory_total_bytes)
          : '—';
      row.querySelector('.d-ifaces').textContent =
        ifaces.length ? up + ' / ' + ifaces.length : '—';
      row.querySelector('.d-down').textContent =
        down.length ? down.map(i => i.name).join(', ') : '—';
      row.querySelector('.d-error').textContent = router.error || '';
    });
    renderAttention(recommendations(seen));
    updated.textContent = 'updated ' + data.generated_at;
    await refreshHistory();
  } catch (err) {
    updated.textContent = 'status error';
  }
}

async function post(url) {
  try { await fetch(url, { method: 'POST' }); } finally { refresh(); }
}

document.getElementById('backup-all').addEventListener('click', event => {
  if (!confirm('Back up every router now?')) return;
  event.target.disabled = true;
  post('api/backups').finally(() => { event.target.disabled = false; });
});

document.querySelectorAll('button.backup').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!confirm('Back up ' + btn.dataset.router + ' now?')) return;
    btn.disabled = true;
    post('api/backups/' + encodeURIComponent(btn.dataset.router))
      .finally(() => { btn.disabled = false; });
  });
});

refresh();
setInterval(refresh, 30000);
"""


def render_dashboard(config: AppConfig, *, show_logout: bool = False) -> str:
    """Render the dashboard shell; live data is filled in by ``/api/status``."""
    cards = "\n".join(
        f"""<article class="card" data-router="{_escape(router.name)}" data-state="unknown">
<div class="card-head">
<div><strong class="card-name">{_escape(router.name)}</strong><br><small>{_escape(router.host)}</small></div>
<span class="badge unknown status">unknown</span>
</div>
<div class="metrics">
<div class="metric"><span class="label">CPU</span><span class="value cpu">—</span><span class="note cpu-note"></span></div>
<div class="metric"><span class="label">Memory free</span><span class="value mem">—</span><span class="note mem-note"></span></div>
<div class="metric"><span class="label">Temperature</span><span class="value temp">—</span><span class="note temp-note"></span></div>
<div class="metric"><span class="label">Interfaces up</span><span class="value ifaces">—</span><span class="note ifaces-note"></span></div>
</div>
<svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none" role="img" aria-label="CPU and memory trend, last 24 hours">
<polyline class="cpu" points=""></polyline>
<polyline class="mem" points=""></polyline>
</svg>
<p class="error"></p>
<div class="card-actions"><button class="backup" data-router="{_escape(router.name)}">Back up</button></div>
</article>"""
        for router in config.routers
    )
    rows = "\n".join(
        f"""<tr data-detail-router="{_escape(router.name)}">
<td><strong>{_escape(router.name)}</strong><br><small>{_escape(router.host)}</small></td>
<td class="d-status">—</td>
<td class="d-temp">—</td>
<td class="d-cpu">—</td>
<td class="d-mem">—</td>
<td class="d-ifaces">—</td>
<td class="d-down">—</td>
<td class="d-error"></td>
</tr>"""
        for router in config.routers
    )
    logout = (
        '<form method="post" action="/logout"><button type="submit">Log out</button></form>'
        if show_logout
        else ""
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
<div class="topbar">
<div>
<h1>ROS Manager</h1>
<p class="meta">{len(config.routers)} router(s) · <span id="updated">loading…</span></p>
</div>
<div class="actions">
<button id="backup-all">Back up all</button>
{logout}
</div>
</div>
<section id="attention" class="attention ok">
<h2>Needs attention</h2>
<ul id="attention-list"><li>Checking routers…</li></ul>
</section>
<section class="cards">
{cards}
</section>
<details class="legend">
<summary>What do these numbers mean?</summary>
<ul>
<li><strong>CPU</strong> — under 50% is light, 50–79% is moderate, 80% or more is high (move heavy rules to another router).</li>
<li><strong>Memory free</strong> — below 15% of total is low; below 10% is critical.</li>
<li><strong>Temperature</strong> — under 55°C is cool, 55–69°C is warm but normal, 70°C or more needs a ventilation check. Some models have no sensor.</li>
<li><strong>Interfaces up</strong> — running interfaces compared with the total. A disabled interface is not counted as down.</li>
<li><strong>Trend lines</strong> — blue is CPU, dashed purple is free memory, for the last 24 hours.</li>
</ul>
</details>
<section class="detail">
<details>
<summary>Raw metrics and interfaces (advanced)</summary>
<table>
<thead><tr>
<th>Router</th><th>Status</th><th>Temp</th><th>CPU</th><th>Memory</th>
<th>Interfaces</th><th>Down</th><th>Error</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</details>
</section>
<script>
{_DASHBOARD_JS}
</script>
</body>
</html>
"""


def render_login_page(error: Optional[str] = None) -> str:
    """Simple password form shown when the dashboard requires a login."""
    message = f'<p class="error">{_escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROS Manager login</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="login">
<h1>ROS Manager</h1>
<p class="meta">Enter the team dashboard password to continue.</p>
{message}
<form method="post" action="/login">
<label for="password">Password</label>
<input id="password" name="password" type="password" autocomplete="current-password" required autofocus>
<button type="submit">Log in</button>
</form>
</div>
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
