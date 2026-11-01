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
/* =====================================================================
   ROS Manager Dashboard – Design System
   Inspired by Finance Management Dashboard (Bogdan Falin / QClay)
   Deep Obsidian Dark Theme · Fintech-grade Enterprise SaaS Aesthetic
   ===================================================================== */

:root {
  --bg:          #090D18;
  --surface:     #0F1629;
  --surface-2:   #141C33;
  --border:      rgba(255,255,255,.07);
  --border-2:    rgba(255,255,255,.12);
  --text:        #E8EDF8;
  --text-muted:  #6B7A99;
  --text-dim:    #3D4F72;

  /* Status palette */
  --ok:          #10B981;
  --ok-dim:      rgba(16,185,129,.15);
  --ok-glow:     rgba(16,185,129,.4);
  --warn:        #F59E0B;
  --warn-dim:    rgba(245,158,11,.15);
  --error:       #F43F5E;
  --error-dim:   rgba(244,63,94,.15);
  --error-glow:  rgba(244,63,94,.4);
  --unknown:     #6B7A99;
  --unknown-dim: rgba(107,122,153,.15);

  /* Brand / accent */
  --accent:      #6366F1;
  --accent-2:    #8B5CF6;
  --accent-dim:  rgba(99,102,241,.15);
  --accent-glow: rgba(99,102,241,.35);

  /* Chart colors */
  --chart-cpu:   #6366F1;
  --chart-mem:   #8B5CF6;

  --r-sm:  .5rem;
  --r-md:  .75rem;
  --r-lg:  1rem;
  --r-xl:  1.25rem;
}

*, *::before, *::after { box-sizing: border-box; }
html { height: 100%; }
body {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  margin: 0; padding: 0; line-height: 1.5;
  background: var(--bg); color: var(--text);
  min-height: 100vh; -webkit-font-smoothing: antialiased;
}
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

/* ── Sidebar ── */
.sidebar {
  position: fixed; inset-y: 0; left: 0; width: 240px; z-index: 40;
  background: var(--surface); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; padding: 1.5rem 1rem;
}
.sidebar-brand { display: flex; align-items: center; gap: .6rem; padding: .25rem .5rem; margin-bottom: .5rem; }
.sidebar-brand-icon {
  width: 32px; height: 32px; border-radius: .5rem;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  box-shadow: 0 0 16px var(--accent-glow);
}
.sidebar-brand-text { font-size: .95rem; font-weight: 700; letter-spacing: -.01em; }
.sidebar-brand-sub  { font-size: .7rem; color: var(--text-muted); margin-top: .1rem; }
.nav-section-label {
  font-size: .65rem; text-transform: uppercase; letter-spacing: .08em;
  color: var(--text-dim); padding: 0 .5rem; margin: 1.5rem 0 .4rem;
}
.nav-link {
  display: flex; align-items: center; gap: .65rem; padding: .55rem .75rem;
  border-radius: var(--r-md); font-size: .83rem; font-weight: 500;
  color: var(--text-muted); text-decoration: none; cursor: pointer;
  transition: background .15s, color .15s; user-select: none;
}
.nav-link:hover  { background: var(--surface-2); color: var(--text); }
.nav-link.active { background: var(--accent-dim); color: var(--text);
                   box-shadow: inset 2px 0 0 var(--accent); }
.nav-link svg { flex-shrink: 0; opacity: .7; }
.nav-link.active svg { opacity: 1; }
.sidebar-footer {
  margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--border);
}
.sfs-label { font-size: .7rem; color: var(--text-muted); margin-bottom: .4rem; }
.sfs-stats { display: flex; gap: .75rem; }
.sfs-stat  { display: flex; flex-direction: column; }
.sfs-stat .num { font-size: 1rem; font-weight: 700; }
.sfs-stat .lbl { font-size: .65rem; color: var(--text-muted); }
.sfs-stat.ok  .num { color: var(--ok); }
.sfs-stat.err .num { color: var(--error); }

/* ── Main layout ── */
.main-wrap { margin-left: 240px; display: flex; flex-direction: column; min-height: 100vh; }

/* ── Top Header ── */
.topheader {
  position: sticky; top: 0; z-index: 30;
  background: rgba(9,13,24,.88);
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
  border-bottom: 1px solid var(--border);
  padding: .85rem 1.5rem;
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
}
.topheader-left { display: flex; align-items: center; gap: .75rem; min-width: 0; }
.topheader-title { font-size: 1rem; font-weight: 600; letter-spacing: -.01em; }
.topheader-sub {
  font-size: .72rem; color: var(--text-muted);
  display: flex; align-items: center; gap: .4rem; margin-top: .1rem;
}
.live-dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--ok); flex-shrink: 0;
  box-shadow: 0 0 0 0 var(--ok-glow); animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
  0%   { box-shadow: 0 0 0 0   var(--ok-glow); }
  70%  { box-shadow: 0 0 0 6px transparent; }
  100% { box-shadow: 0 0 0 0   transparent; }
}
.topheader-actions { display: flex; align-items: center; gap: .6rem; flex-shrink: 0; }

/* ── Buttons ── */
.btn {
  display: inline-flex; align-items: center; gap: .4rem;
  padding: .45rem .9rem; border-radius: var(--r-md);
  font-size: .8rem; font-weight: 600; letter-spacing: .01em;
  cursor: pointer; border: none; text-decoration: none;
  transition: opacity .15s, transform .1s, box-shadow .15s; white-space: nowrap;
}
.btn:hover   { opacity: .88; }
.btn:active  { transform: scale(.97); }
.btn:disabled { opacity: .4; cursor: default; transform: none; }
.btn-primary {
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #fff; box-shadow: 0 4px 16px var(--accent-glow);
}
.btn-primary:hover { box-shadow: 0 6px 22px var(--accent-glow); }
.btn-ghost {
  background: var(--surface-2); border: 1px solid var(--border-2); color: var(--text-muted);
}
.btn-ghost:hover { color: var(--text); border-color: rgba(255,255,255,.2); }
.btn-danger {
  background: var(--error-dim); border: 1px solid rgba(244,63,94,.3); color: var(--error);
}
.btn-sm { padding: .3rem .65rem; font-size: .72rem; }

/* ── KPI Cards ── */
.kpi-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem; padding: 1.5rem 1.5rem 0;
}
.kpi-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-xl); padding: 1.1rem 1.25rem;
  position: relative; overflow: hidden; transition: border-color .2s, transform .2s;
}
.kpi-card:hover { border-color: var(--border-2); transform: translateY(-1px); }
.kpi-card::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse at top left, var(--kpi-glow, transparent) 0%, transparent 65%);
  opacity: .3; pointer-events: none;
}
.kpi-card.kpi-total { --kpi-glow: var(--accent); }
.kpi-card.kpi-ok    { --kpi-glow: var(--ok); }
.kpi-card.kpi-alert { --kpi-glow: var(--error); }
.kpi-card.kpi-cpu   { --kpi-glow: var(--accent-2); }
.kpi-label {
  font-size: .65rem; text-transform: uppercase; letter-spacing: .08em;
  color: var(--text-muted); font-weight: 600; margin-bottom: .5rem;
}
.kpi-row { display: flex; align-items: flex-end; justify-content: space-between; }
.kpi-value { font-size: 2rem; font-weight: 800; letter-spacing: -.03em; line-height: 1; color: var(--text); }
.kpi-icon {
  width: 36px; height: 36px; border-radius: var(--r-md);
  display: flex; align-items: center; justify-content: center;
}
.kpi-card.kpi-total .kpi-icon { background: var(--accent-dim); }
.kpi-card.kpi-ok    .kpi-icon { background: var(--ok-dim); }
.kpi-card.kpi-alert .kpi-icon { background: var(--error-dim); }
.kpi-card.kpi-cpu   .kpi-icon { background: rgba(139,92,246,.15); }
.kpi-sub { font-size: .7rem; color: var(--text-muted); margin-top: .3rem; }

/* ── Alerts panel ── */
.alerts-panel {
  margin: 1rem 1.5rem 0; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-xl); overflow: hidden;
}
.alerts-panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: .9rem 1.25rem; border-bottom: 1px solid var(--border);
}
.alerts-panel-title { font-size: .8rem; font-weight: 700; display: flex; align-items: center; gap: .5rem; }
.alerts-badge { font-size: .65rem; font-weight: 700; padding: .15rem .5rem;
                border-radius: 99px; background: var(--error-dim); color: var(--error); }
.alerts-badge.ok { background: var(--ok-dim); color: var(--ok); }
.alerts-body { padding: .75rem 1.25rem; display: flex; flex-direction: column; gap: .4rem; }
.alert-item {
  display: flex; align-items: flex-start; gap: .65rem;
  padding: .6rem .75rem; border-radius: var(--r-md);
  border: 1px solid transparent; transition: background .15s;
}
.alert-item.alert-ok    { background: var(--ok-dim);    border-color: rgba(16,185,129,.2); }
.alert-item.alert-warn  { background: var(--warn-dim);  border-color: rgba(245,158,11,.2); }
.alert-item.alert-error { background: var(--error-dim); border-color: rgba(244,63,94,.2); }
.alert-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: .35rem;
}
.alert-item.alert-ok   .alert-dot { background: var(--ok); }
.alert-item.alert-warn .alert-dot { background: var(--warn); }
.alert-item.alert-error .alert-dot { background: var(--error); }
.alert-text { font-size: .78rem; color: var(--text); line-height: 1.5; }

/* ── Router cards ── */
.cards-section { padding: 1rem 1.5rem 0; }
.cards-section-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: .75rem;
}
.section-title { font-size: .75rem; font-weight: 700; color: var(--text-muted);
                  text-transform: uppercase; letter-spacing: .06em; }
.router-search {
  display: flex; align-items: center; gap: .5rem;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-md); padding: .35rem .75rem; transition: border-color .15s;
}
.router-search:focus-within { border-color: var(--accent); }
.router-search svg { opacity: .4; flex-shrink: 0; }
.router-search input {
  background: none; border: none; outline: none;
  color: var(--text); font-size: .78rem; width: 160px;
}
.router-search input::placeholder { color: var(--text-muted); }
.cards-grid {
  display: grid; gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}

/* ── Device card ── */
article.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-xl); padding: 1.1rem 1.15rem 1rem;
  display: flex; flex-direction: column; gap: .85rem;
  transition: border-color .2s, transform .2s, box-shadow .2s;
  position: relative; overflow: hidden;
}
article.card:hover {
  border-color: var(--border-2); transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(0,0,0,.35);
}
article.card::after {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  border-radius: var(--r-xl) var(--r-xl) 0 0;
  background: var(--state-color, var(--text-dim)); transition: background .3s;
}
article.card[data-state="ok"]      { --state-color: var(--ok); }
article.card[data-state="warn"]    { --state-color: var(--warn); }
article.card[data-state="error"]   { --state-color: var(--error); }
article.card[data-state="unknown"] { --state-color: var(--text-dim); }

.card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: .5rem; }
.card-title-wrap { display: flex; align-items: center; gap: .65rem; min-width: 0; }
.card-device-icon {
  width: 34px; height: 34px; border-radius: var(--r-md); flex-shrink: 0;
  background: var(--surface-2); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
}
.card-name { font-size: .88rem; font-weight: 700; letter-spacing: -.01em;
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-host { font-size: .68rem; color: var(--text-muted); margin-top: .05rem;
             font-family: 'Menlo','Consolas',monospace; }

.status-badge {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .2rem .55rem; border-radius: 99px;
  font-size: .65rem; font-weight: 700; letter-spacing: .03em;
  text-transform: uppercase; flex-shrink: 0; white-space: nowrap;
}
.status-badge .dot { width: 5px; height: 5px; border-radius: 50%; }
.status-badge.badge-ok      { background: var(--ok-dim);      color: var(--ok); }
.status-badge.badge-ok .dot { background: var(--ok);
                               box-shadow: 0 0 0 0 var(--ok-glow); animation: pulse-dot 2s infinite; }
.status-badge.badge-warn    { background: var(--warn-dim);    color: var(--warn); }
.status-badge.badge-warn .dot { background: var(--warn); }
.status-badge.badge-error   { background: var(--error-dim);   color: var(--error); }
.status-badge.badge-error .dot { background: var(--error);
                                  box-shadow: 0 0 0 0 var(--error-glow); animation: pulse-dot 2s infinite; }
.status-badge.badge-unknown { background: var(--unknown-dim); color: var(--unknown); }
.status-badge.badge-unknown .dot { background: var(--unknown); }

.gauge-row { display: flex; flex-direction: column; gap: .5rem; }
.gauge-item { display: flex; flex-direction: column; gap: .25rem; }
.gauge-header { display: flex; justify-content: space-between; align-items: center; }
.gauge-label { font-size: .65rem; text-transform: uppercase; letter-spacing: .07em;
               color: var(--text-muted); font-weight: 600; }
.gauge-value { font-size: .78rem; font-weight: 700; }
.gauge-note  { font-size: .65rem; color: var(--text-muted); }
.gauge-bar-bg { height: 4px; border-radius: 99px; background: var(--surface-2); overflow: hidden; }
.gauge-bar-fill {
  height: 100%; border-radius: 99px;
  background: var(--gauge-color, var(--accent));
  width: 0%; transition: width .6s cubic-bezier(.4,0,.2,1), background .3s;
}

.ifaces-row { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
.ifaces-value { font-size: .8rem; font-weight: 700; }
.ifaces-note  { font-size: .65rem; color: var(--text-muted); }

.spark-legend { display: flex; gap: .8rem; margin-bottom: .2rem; }
.spark-legend-item { display: flex; align-items: center; gap: .3rem;
                     font-size: .62rem; color: var(--text-muted); }
.spark-legend-line { width: 14px; height: 2px; border-radius: 1px; }
.spark { width: 100%; height: 40px; display: block; overflow: visible; }
.spark polyline { fill: none; stroke-width: 1.8; vector-effect: non-scaling-stroke; }
.spark .cpu { stroke: var(--chart-cpu); }
.spark .mem { stroke: var(--chart-mem); stroke-dasharray: 4 3; }

.card-error { font-size: .72rem; color: var(--error); min-height: .8em; word-break: break-all; }
.card-actions {
  display: flex; gap: .5rem; padding-top: .6rem; border-top: 1px solid var(--border);
}

/* ── Detail table ── */
.table-section { margin: 1rem 1.5rem 1.5rem; }
.table-wrap { background: var(--surface); border: 1px solid var(--border);
              border-radius: var(--r-xl); overflow: hidden; }
.detail-table { border-collapse: collapse; width: 100%; }
.detail-table th {
  background: var(--surface-2); font-size: .62rem; text-transform: uppercase;
  letter-spacing: .08em; color: var(--text-muted); font-weight: 700;
  padding: .65rem 1rem; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap;
}
.detail-table td { padding: .7rem 1rem; font-size: .78rem;
                   border-bottom: 1px solid var(--border); vertical-align: middle; }
.detail-table tbody tr:last-child td { border-bottom: none; }
.detail-table tbody tr { transition: background .12s; }
.detail-table tbody tr:hover { background: var(--surface-2); }
.detail-table .mono { font-family: 'Menlo','Consolas',monospace; font-size: .72rem; color: var(--text-muted); }
.tbl-badge {
  display: inline-flex; align-items: center; gap: .3rem;
  padding: .15rem .5rem; border-radius: 99px;
  font-size: .62rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
}
.tbl-badge.ok      { background: var(--ok-dim);      color: var(--ok); }
.tbl-badge.warn    { background: var(--warn-dim);     color: var(--warn); }
.tbl-badge.error   { background: var(--error-dim);    color: var(--error); }
.tbl-badge.unknown { background: var(--unknown-dim);  color: var(--unknown); }

/* ── Legend ── */
.legend-section { margin: 0 1.5rem 2rem; background: var(--surface);
                  border: 1px solid var(--border); border-radius: var(--r-xl); overflow: hidden; }
.legend-toggle {
  width: 100%; text-align: left; background: none; border: none;
  padding: .9rem 1.25rem; cursor: pointer; color: var(--text-muted);
  font-size: .78rem; font-weight: 600; display: flex; align-items: center; gap: .5rem;
}
.legend-toggle:hover { color: var(--text); }
.legend-body { padding: 0 1.25rem 1rem; }
.legend-body ul { margin: 0; padding-left: 1.1rem; }
.legend-body li { font-size: .75rem; color: var(--text-muted); margin-bottom: .35rem; }
.legend-body li strong { color: var(--text); }

/* ── Login ── */
.login-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: var(--bg); padding: 1.5rem;
}
.login-card {
  width: 100%; max-width: 380px; background: var(--surface);
  border: 1px solid var(--border); border-radius: var(--r-xl); padding: 2.5rem 2rem;
}
.login-icon {
  width: 48px; height: 48px; border-radius: var(--r-lg);
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  display: flex; align-items: center; justify-content: center; margin-bottom: 1.25rem;
  box-shadow: 0 0 24px var(--accent-glow);
}
.login-title { font-size: 1.3rem; font-weight: 800; letter-spacing: -.02em; }
.login-sub   { font-size: .8rem; color: var(--text-muted); margin: .3rem 0 1.5rem; }
.login-label { font-size: .75rem; font-weight: 600; color: var(--text-muted); display: block; margin-bottom: .4rem; }
.login-input {
  width: 100%; padding: .6rem .85rem;
  background: var(--surface-2); border: 1px solid var(--border-2);
  border-radius: var(--r-md); color: var(--text); font-size: .85rem;
  outline: none; transition: border-color .15s; margin-bottom: 1rem;
}
.login-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); }
.login-error {
  font-size: .75rem; color: var(--error); background: var(--error-dim);
  border: 1px solid rgba(244,63,94,.3); border-radius: var(--r-sm);
  padding: .5rem .75rem; margin-bottom: 1rem;
}

/* ── Error ── */
.error-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: var(--bg); padding: 1.5rem;
}
.error-card {
  max-width: 460px; width: 100%; background: var(--surface);
  border: 1px solid rgba(244,63,94,.25); border-radius: var(--r-xl); padding: 2rem;
}
.error-card h1 { font-size: 1.1rem; font-weight: 700; margin: 0 0 .75rem; }
.error-msg {
  font-size: .82rem; color: var(--error); background: var(--error-dim);
  border: 1px solid rgba(244,63,94,.2); border-radius: var(--r-md);
  padding: .75rem 1rem; word-break: break-all;
}

/* ── Static report ── */
.report-wrap { padding: 1.5rem; }
.report-title { font-size: 1.3rem; font-weight: 800; letter-spacing: -.02em; margin-bottom: .25rem; }
.report-meta  { font-size: .75rem; color: var(--text-muted); margin-bottom: 1.5rem; }
table.report {
  border-collapse: collapse; width: 100%; background: var(--surface);
  border-radius: var(--r-lg); overflow: hidden; border: 1px solid var(--border);
}
table.report th {
  background: var(--surface-2); font-size: .62rem; text-transform: uppercase;
  letter-spacing: .08em; color: var(--text-muted); font-weight: 700;
  padding: .65rem 1rem; border-bottom: 1px solid var(--border); text-align: left;
}
table.report td { padding: .65rem 1rem; font-size: .78rem;
                  border-bottom: 1px solid var(--border); vertical-align: middle; }
table.report tbody tr:last-child td { border-bottom: none; }
table.report tbody tr:hover { background: var(--surface-2); }

/* ── Responsive ── */
@media (max-width: 768px) {
  .sidebar   { display: none; }
  .main-wrap { margin-left: 0; }
  .kpi-grid  { padding: 1rem; grid-template-columns: repeat(2, 1fr); }
  .cards-section, .table-section, .alerts-panel, .legend-section {
    margin-left: .75rem; margin-right: .75rem;
  }
  .topheader { padding: .75rem 1rem; }
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

    def _report_badge(status: Optional[str]) -> str:
        status = status or "unknown"
        css = status if status in {"ok", "error"} else "unknown"
        return f'<span class="report-badge {css}">{_escape(status)}</span>'

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
            f'<span style="font-family:monospace;font-size:.72rem;color:var(--text-muted)">{_escape(entry["host"])}</span></td>',
            f"<td>{_report_badge(entry['status'])}</td>",
            f"<td>{_escape(entry['temperature_c'])}</td>",
            f"<td>{_escape(entry['cpu_load_percent'])}</td>",
            f"<td>{memory}</td>",
            f"<td>{'—' if total is None else f'{up}/{total}'}</td>",
            f'<td style="color:var(--error);font-size:.72rem">{_escape(entry["error"])}</td>',
        ]
        if include_backup:
            backup = entry.get("backup", {})
            cells += [
                f"<td>{_report_badge(backup.get('status'))}</td>",
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
<div class="report-wrap">
<div class="report-title">{_escape(title)}</div>
<div class="report-meta">Generated at {_escape(generated_at())} &middot; {len(results)} router(s)</div>
<table class="report">
<thead><tr>{header_html}</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</div>
</body>
</html>
"""



_DASHBOARD_JS = """
/* ── Thresholds ── */
const THRESHOLDS = {
  cpuWarn: 80, cpuHigh: 90,
  memLowPct: 15, memCriticalPct: 10,
  tempWarn: 70, tempHot: 80,
};

/* ── Formatters ── */
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

/* ── Threshold notes ── */
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

/* ── Gauge bar color logic ── */
function cpuGaugeColor(v) {
  if (v === null || v === undefined) return 'var(--accent)';
  if (v >= THRESHOLDS.cpuHigh) return 'var(--error)';
  if (v >= THRESHOLDS.cpuWarn) return 'var(--warn)';
  return 'var(--accent)';
}
function memGaugeColor(free, total) {
  if (!total || free === null || free === undefined) return 'var(--chart-mem)';
  const pct = free / total * 100;
  if (pct < THRESHOLDS.memCriticalPct) return 'var(--error)';
  if (pct < THRESHOLDS.memLowPct)      return 'var(--warn)';
  return 'var(--chart-mem)';
}
function tempGaugeColor(v) {
  if (v === null || v === undefined) return 'var(--ok)';
  if (v >= THRESHOLDS.tempHot)  return 'var(--error)';
  if (v >= THRESHOLDS.tempWarn) return 'var(--warn)';
  return 'var(--ok)';
}

/* ── State helper ── */
function stateFor(router) {
  if (router.status !== 'ok') return 'error';
  const total = router.memory_total_bytes;
  const memPct = (router.memory_free_bytes !== null
    && router.memory_free_bytes !== undefined && total)
    ? router.memory_free_bytes / total * 100 : null;
  if ((router.cpu_load_percent !== null && router.cpu_load_percent >= THRESHOLDS.cpuWarn)
      || (memPct !== null && memPct < THRESHOLDS.memLowPct)
      || (router.temperature_c !== null && router.temperature_c >= THRESHOLDS.tempWarn)
      || downInterfaces(router).length > 0) {
    return 'warn';
  }
  return 'ok';
}

/* ── Apply card data ── */
function applyCard(card, router) {
  const state = stateFor(router);
  card.dataset.state = state;

  // Status badge
  const badge = card.querySelector('.status-badge');
  const stateMap = { error: ['badge-error', 'error'], warn: ['badge-warn', 'warning'], ok: ['badge-ok', 'ok'] };
  const [cls, label] = stateMap[state] || ['badge-unknown', 'unknown'];
  badge.className = 'status-badge ' + cls;
  badge.querySelector('.badge-label').textContent = label;

  // CPU gauge
  const cpu = router.cpu_load_percent;
  const cpuFill = card.querySelector('.cpu-fill');
  const cpuVal  = card.querySelector('.cpu-val');
  const cpuNote_ = card.querySelector('.cpu-note');
  if (cpu !== null && cpu !== undefined) {
    cpuVal.textContent = cpu + ' %';
    cpuFill.style.width = Math.min(cpu, 100) + '%';
    cpuFill.style.setProperty('--gauge-color', cpuGaugeColor(cpu));
    cpuFill.style.background = cpuGaugeColor(cpu);
  } else {
    cpuVal.textContent = '—';
    cpuFill.style.width = '0%';
  }
  if (cpuNote_) cpuNote_.textContent = cpuNote(cpu);

  // Memory gauge
  const memFree  = router.memory_free_bytes;
  const memTotal = router.memory_total_bytes;
  const memFill  = card.querySelector('.mem-fill');
  const memVal   = card.querySelector('.mem-val');
  const memNote_ = card.querySelector('.mem-note');
  if (memFree !== null && memFree !== undefined && memTotal) {
    const usedPct = ((memTotal - memFree) / memTotal) * 100;
    memVal.textContent = fmtBytes(memFree) + ' free';
    memFill.style.width = Math.min(usedPct, 100) + '%';
    memFill.style.background = memGaugeColor(memFree, memTotal);
  } else {
    memVal.textContent = '—';
    memFill.style.width = '0%';
  }
  if (memNote_) memNote_.textContent = memNote(memFree, memTotal);

  // Temp gauge
  const temp     = router.temperature_c;
  const tempFill = card.querySelector('.temp-fill');
  const tempVal  = card.querySelector('.temp-val');
  const tempNote_ = card.querySelector('.temp-note');
  if (temp !== null && temp !== undefined) {
    tempVal.textContent = temp + ' °C';
    const pct = Math.min(temp / 100, 1) * 100;
    tempFill.style.width = pct + '%';
    tempFill.style.background = tempGaugeColor(temp);
  } else {
    tempVal.textContent = '—';
    tempFill.style.width = '0%';
  }
  if (tempNote_) tempNote_.textContent = tempNote(temp);

  // Interfaces
  const ifaces = Array.isArray(router.interfaces) ? router.interfaces : [];
  const up = ifaces.filter(i => i.running === true).length;
  const down = downInterfaces(router);
  const ifacesEl = card.querySelector('.ifaces-value');
  const ifaceNoteEl = card.querySelector('.ifaces-note');
  ifacesEl.textContent = ifaces.length ? up + ' / ' + ifaces.length : '—';
  if (ifaceNoteEl) {
    ifaceNoteEl.textContent = down.length
      ? down.length + ' down: ' + down.map(i => i.name).join(', ')
      : (ifaces.length ? 'all interfaces up' : '');
  }

  // Error
  const errEl = card.querySelector('.card-error');
  if (errEl) errEl.textContent = router.error || '';
}

/* ── Recommendations ── */
function recommendations(routers) {
  const items = [];
  routers.forEach(router => {
    if (router.status !== 'ok') {
      items.push({ level: 'error',
        text: router.name + ' is not responding — check power and network.'
          + (router.error ? ' (' + router.error + ')' : '') });
      return;
    }
    if (router.cpu_load_percent !== null && router.cpu_load_percent >= THRESHOLDS.cpuWarn) {
      items.push({ level: 'warn',
        text: router.name + ' CPU at ' + router.cpu_load_percent
          + '% — move heavy firewall rules or queues to another router.' });
    }
    const total = router.memory_total_bytes;
    if (router.memory_free_bytes !== null && total) {
      const pct = router.memory_free_bytes / total * 100;
      if (pct < THRESHOLDS.memLowPct) {
        items.push({ level: 'warn',
          text: router.name + ' has only ' + pct.toFixed(0)
            + '% free memory — check for runaway processes.' });
      }
    }
    if (router.temperature_c !== null && router.temperature_c >= THRESHOLDS.tempWarn) {
      items.push({ level: 'warn',
        text: router.name + ' at ' + router.temperature_c
          + '°C — check room ventilation and airflow.' });
    }
    downInterfaces(router).forEach(iface => {
      items.push({ level: 'warn',
        text: router.name + ': interface ' + iface.name + ' is down — check the cable.' });
    });
  });
  return items;
}

/* ── Render attention panel ── */
function renderAttention(items) {
  const body  = document.getElementById('attention-body');
  const badge = document.getElementById('attention-badge');
  if (!body) return;
  body.replaceChildren();
  if (!items.length) {
    if (badge) { badge.textContent = 'All clear'; badge.className = 'alerts-badge ok'; }
    const el = document.createElement('div');
    el.className = 'alert-item alert-ok';
    el.innerHTML = '<span class="alert-dot"></span><span class="alert-text">All routers are healthy — no action required.</span>';
    body.appendChild(el);
    return;
  }
  const hasErr = items.some(i => i.level === 'error');
  if (badge) {
    badge.textContent = items.length + (hasErr ? ' critical' : ' warning') + (items.length === 1 ? '' : 's');
    badge.className = 'alerts-badge' + (hasErr ? '' : ' ok').replace(' ok', hasErr ? '' : ' warn');
    badge.style.background = hasErr ? 'var(--error-dim)' : 'var(--warn-dim)';
    badge.style.color = hasErr ? 'var(--error)' : 'var(--warn)';
  }
  items.forEach(item => {
    const el = document.createElement('div');
    el.className = 'alert-item alert-' + item.level;
    el.innerHTML = '<span class="alert-dot"></span><span class="alert-text">' + item.text + '</span>';
    body.appendChild(el);
  });
}

/* ── Sparkline ── */
function polyline(values, maxValue) {
  const present = values.filter(v => v !== null && v !== undefined);
  if (present.length < 2) return '';
  const max = maxValue || Math.max(...present, 1);
  const step = values.length > 1 ? 100 / (values.length - 1) : 0;
  return values.map((value, index) => {
    if (value === null || value === undefined) return null;
    const y = 36 - (Math.min(value, max) / max) * 34;
    return (index * step).toFixed(2) + ',' + y.toFixed(2);
  }).filter(p => p !== null).join(' ');
}
function drawSpark(card, points) {
  const svg = card.querySelector('.spark');
  if (!svg) return;
  const memMax = Math.max(...points.map(p => p.mem_total || 0), 1);
  svg.querySelector('.cpu').setAttribute('points', polyline(points.map(p => p.cpu), 100));
  svg.querySelector('.mem').setAttribute('points', polyline(points.map(p => p.mem_free), memMax));
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
  } catch (e) { /* best effort */ }
}

/* ── KPI update ── */
function updateKpis(data, seen) {
  const totalEl   = document.getElementById('kpi-total');
  const healthyEl = document.getElementById('kpi-healthy');
  const alertsEl  = document.getElementById('kpi-alerts');
  const cpuEl     = document.getElementById('kpi-cpu');
  const sfsTotal  = document.getElementById('sfs-total');
  const sfsOk     = document.getElementById('sfs-ok');
  const sfsErr    = document.getElementById('sfs-err');
  if (!totalEl) return;
  const routers = Array.isArray(data.routers) ? data.routers : [];
  const healthy = routers.filter(r => r.status === 'ok').length;
  const alerts  = routers.filter(r => r.status !== 'ok').length;
  const cpus    = routers.filter(r => r.status === 'ok' && r.cpu_load_percent !== null).map(r => r.cpu_load_percent);
  totalEl.textContent   = String(routers.length);
  healthyEl.textContent = String(healthy);
  alertsEl.textContent  = String(alerts);
  cpuEl.textContent     = (cpus.length ? (cpus.reduce((a, b) => a + b, 0) / cpus.length).toFixed(1) : '—') + ' %';
  if (sfsTotal) sfsTotal.textContent = routers.length;
  if (sfsOk)    sfsOk.textContent    = healthy;
  if (sfsErr)   sfsErr.textContent   = alerts;
}

/* ── Table update ── */
function updateTable(byName) {
  document.querySelectorAll('tr[data-detail-router]').forEach(row => {
    const router = byName[row.dataset.detailRouter];
    if (!router) return;
    const ifaces = Array.isArray(router.interfaces) ? router.interfaces : [];
    const up     = ifaces.filter(i => i.running === true).length;
    const down   = downInterfaces(router);
    const state  = stateFor(router);
    const stateLabel = state === 'error' ? 'error' : (state === 'warn' ? 'warn' : 'ok');
    const tblBadge   = row.querySelector('.tbl-badge');
    if (tblBadge) { tblBadge.textContent = stateLabel; tblBadge.className = 'tbl-badge ' + stateLabel; }
    row.querySelector('.d-temp').textContent = fmt(router.temperature_c, ' °C');
    row.querySelector('.d-cpu').textContent  = fmt(router.cpu_load_percent, ' %');
    row.querySelector('.d-mem').textContent  =
      (router.memory_free_bytes !== null && router.memory_total_bytes !== null)
        ? fmtBytes(router.memory_free_bytes) + ' / ' + fmtBytes(router.memory_total_bytes) : '—';
    row.querySelector('.d-ifaces').textContent = ifaces.length ? up + ' / ' + ifaces.length : '—';
    row.querySelector('.d-down').textContent   = down.length ? down.map(i => i.name).join(', ') : '—';
    row.querySelector('.d-error').textContent  = router.error || '';
  });
}

/* ── Main refresh ── */
async function refresh() {
  const updated = document.getElementById('updated');
  try {
    const res = await fetch('api/status');
    if (res.status === 401) { window.location.href = 'login'; return; }
    if (!res.ok) { if (updated) updated.textContent = 'status error'; return; }
    const data   = await res.json();
    const byName = Object.fromEntries(data.routers.map(r => [r.name, r]));
    const seen   = [];
    document.querySelectorAll('article.card[data-router]').forEach(card => {
      const router = byName[card.dataset.router];
      if (!router) return;
      applyCard(card, router);
      seen.push(router);
    });
    updateTable(byName);
    updateKpis(data, seen);
    renderAttention(recommendations(seen));
    if (updated) updated.textContent = 'synced ' + new Date().toLocaleTimeString();
    await refreshHistory();
  } catch (err) {
    if (updated) updated.textContent = 'connection error';
  }
}

/* ── Backup helpers ── */
async function post(url) {
  try { await fetch(url, { method: 'POST' }); } finally { refresh(); }
}
document.getElementById('backup-all').addEventListener('click', event => {
  if (!confirm('Back up every router now?')) return;
  event.target.disabled = true;
  post('api/backups').finally(() => { event.target.disabled = false; });
});
document.querySelectorAll('button.backup-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    if (!confirm('Back up ' + btn.dataset.router + ' now?')) return;
    btn.disabled = true;
    post('api/backups/' + encodeURIComponent(btn.dataset.router))
      .finally(() => { btn.disabled = false; });
  });
});

/* ── Router search filter ── */
const searchInput = document.getElementById('router-search');
if (searchInput) {
  searchInput.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase();
    document.querySelectorAll('article.card[data-router]').forEach(card => {
      const name = (card.dataset.router || '').toLowerCase();
      const host = (card.querySelector('.card-host') || {}).textContent || '';
      card.style.display = (!q || name.includes(q) || host.toLowerCase().includes(q)) ? '' : 'none';
    });
  });
}

/* ── Legend toggle ── */
const legendToggle = document.getElementById('legend-toggle');
const legendBody   = document.getElementById('legend-body');
if (legendToggle && legendBody) {
  legendBody.style.display = 'none';
  legendToggle.addEventListener('click', () => {
    const open = legendBody.style.display !== 'none';
    legendBody.style.display = open ? 'none' : 'block';
    legendToggle.querySelector('.legend-chevron').style.transform = open ? '' : 'rotate(180deg)';
  });
}

refresh();
setInterval(refresh, 30000);
"""



def render_dashboard(config: AppConfig, *, show_logout: bool = False) -> str:
    """Render the dashboard shell; live data is filled in by ``/api/status``."""

    # ── Sidebar nav icon SVGs (Lucide-style inline) ──
    icon_overview = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>'
    icon_router   = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="8" rx="2"/><path d="M6 10h.01M10 10h.01"/><path d="M12 18v-4"/><path d="M8 18h8"/></svg>'
    icon_backup   = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
    icon_alert    = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'

    # ── KPI icons ──
    icon_fleet  = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="8" rx="2"/><path d="M6 10h.01M10 10h.01"/></svg>'
    icon_health = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
    icon_warn   = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    icon_cpu    = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>'

    # ── Device icon (generic router) ──
    icon_device = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--text-muted)"><rect x="2" y="6" width="20" height="8" rx="2"/><path d="M6 10h.01M10 10h.01"/><path d="M12 18v-4"/><path d="M8 18h8"/></svg>'

    # ── Logout button ──
    logout_btn = (
        '<form method="post" action="/logout" style="margin:0">'
        '<button type="submit" class="btn btn-ghost btn-sm">Log out</button>'
        '</form>'
        if show_logout else ""
    )

    # ── Router cards ──
    cards = "\n".join(
        f"""<article class="card" data-router="{_escape(router.name)}" data-state="unknown">
  <div class="card-head">
    <div class="card-title-wrap">
      <div class="card-device-icon">{icon_device}</div>
      <div>
        <div class="card-name">{_escape(router.name)}</div>
        <div class="card-host">{_escape(router.host)}</div>
      </div>
    </div>
    <span class="status-badge badge-unknown">
      <span class="dot"></span>
      <span class="badge-label">unknown</span>
    </span>
  </div>

  <div class="gauge-row">
    <div class="gauge-item">
      <div class="gauge-header">
        <span class="gauge-label">CPU Load</span>
        <span class="gauge-value cpu-val">—</span>
      </div>
      <div class="gauge-bar-bg"><div class="gauge-bar-fill cpu-fill" style="background:var(--accent)"></div></div>
      <div class="gauge-note cpu-note"></div>
    </div>
    <div class="gauge-item">
      <div class="gauge-header">
        <span class="gauge-label">Memory Free</span>
        <span class="gauge-value mem-val">—</span>
      </div>
      <div class="gauge-bar-bg"><div class="gauge-bar-fill mem-fill" style="background:var(--chart-mem)"></div></div>
      <div class="gauge-note mem-note"></div>
    </div>
    <div class="gauge-item">
      <div class="gauge-header">
        <span class="gauge-label">Temperature</span>
        <span class="gauge-value temp-val">—</span>
      </div>
      <div class="gauge-bar-bg"><div class="gauge-bar-fill temp-fill" style="background:var(--ok)"></div></div>
      <div class="gauge-note temp-note"></div>
    </div>
  </div>

  <div class="ifaces-row">
    <div>
      <div class="gauge-label">Interfaces Up</div>
      <div class="ifaces-value">—</div>
    </div>
    <div class="ifaces-note" style="text-align:right"></div>
  </div>

  <div>
    <div class="spark-legend">
      <span class="spark-legend-item">
        <span class="spark-legend-line" style="background:var(--chart-cpu)"></span> CPU
      </span>
      <span class="spark-legend-item">
        <span class="spark-legend-line" style="background:var(--chart-mem);opacity:.7;border-top:1px dashed var(--chart-mem);height:0"></span> Mem
      </span>
    </div>
    <svg class="spark" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="CPU and memory trend, last 24 hours">
      <polyline class="cpu" points=""></polyline>
      <polyline class="mem" points=""></polyline>
    </svg>
  </div>

  <p class="card-error"></p>

  <div class="card-actions">
    <button class="btn btn-ghost btn-sm backup-btn" data-router="{_escape(router.name)}">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Back up
    </button>
  </div>
</article>"""
        for router in config.routers
    )

    # ── Detail table rows ──
    rows = "\n".join(
        f"""<tr data-detail-router="{_escape(router.name)}">
  <td class="cell-name">
    <strong>{_escape(router.name)}</strong><br>
    <span class="mono">{_escape(router.host)}</span>
  </td>
  <td><span class="tbl-badge unknown">—</span></td>
  <td class="d-temp">—</td>
  <td class="d-cpu">—</td>
  <td class="d-mem">—</td>
  <td class="d-ifaces">—</td>
  <td class="d-down">—</td>
  <td class="d-error" style="color:var(--error);font-size:.72rem"></td>
</tr>"""
        for router in config.routers
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROS Manager — Fleet Dashboard</title>
<script src="/static/tailwind.min.js"></script>
<style>{_STYLE}</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════
     SIDEBAR
═══════════════════════════════════════════════ -->
<aside class="sidebar">
  <div class="sidebar-brand">
    <div class="sidebar-brand-icon">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="6" width="20" height="8" rx="2"/>
        <path d="M6 10h.01M10 10h.01"/>
        <path d="M12 18v-4"/><path d="M8 18h8"/>
      </svg>
    </div>
    <div>
      <div class="sidebar-brand-text">ROS Manager</div>
      <div class="sidebar-brand-sub">MikroTik Fleet</div>
    </div>
  </div>

  <div class="nav-section-label">Navigation</div>
  <nav>
    <a href="/" class="nav-link active">{icon_overview} Overview</a>
    <a href="/" class="nav-link">{icon_router} Routers</a>
    <a href="/" class="nav-link">{icon_backup} Backups</a>
    <a href="/" class="nav-link">{icon_alert} Alerts</a>
  </nav>

  <div class="sidebar-footer">
    <div class="sfs-label">Fleet at a glance</div>
    <div class="sfs-stats">
      <div class="sfs-stat ttl">
        <span class="num" id="sfs-total">—</span>
        <span class="lbl">Total</span>
      </div>
      <div class="sfs-stat ok">
        <span class="num" id="sfs-ok">—</span>
        <span class="lbl">Online</span>
      </div>
      <div class="sfs-stat err">
        <span class="num" id="sfs-err">—</span>
        <span class="lbl">Alert</span>
      </div>
    </div>
  </div>
</aside>

<!-- ═══════════════════════════════════════════════
     MAIN CONTENT
═══════════════════════════════════════════════ -->
<div class="main-wrap">

  <!-- Top Header -->
  <header class="topheader">
    <div class="topheader-left">
      <div>
        <div class="topheader-title">Fleet Dashboard</div>
        <div class="topheader-sub">
          <span class="live-dot"></span>
          {len(config.routers)} router(s) monitored &middot; <span id="updated">loading&hellip;</span>
        </div>
      </div>
    </div>
    <div class="topheader-actions">
      <button id="backup-all" class="btn btn-primary">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        Back up all
      </button>
      {logout_btn}
    </div>
  </header>

  <!-- KPI Stats -->
  <section class="kpi-grid">
    <div class="kpi-card kpi-total">
      <div class="kpi-label">Fleet Size</div>
      <div class="kpi-row">
        <div class="kpi-value" id="kpi-total">—</div>
        <div class="kpi-icon">{icon_fleet}</div>
      </div>
      <div class="kpi-sub">routers tracked</div>
    </div>
    <div class="kpi-card kpi-ok">
      <div class="kpi-label">Healthy</div>
      <div class="kpi-row">
        <div class="kpi-value" id="kpi-healthy">—</div>
        <div class="kpi-icon">{icon_health}</div>
      </div>
      <div class="kpi-sub">responding now</div>
    </div>
    <div class="kpi-card kpi-alert">
      <div class="kpi-label">Alerts</div>
      <div class="kpi-row">
        <div class="kpi-value" id="kpi-alerts">—</div>
        <div class="kpi-icon">{icon_warn}</div>
      </div>
      <div class="kpi-sub">need attention</div>
    </div>
    <div class="kpi-card kpi-cpu">
      <div class="kpi-label">Avg CPU</div>
      <div class="kpi-row">
        <div class="kpi-value" id="kpi-cpu">—</div>
        <div class="kpi-icon">{icon_cpu}</div>
      </div>
      <div class="kpi-sub">fleet average</div>
    </div>
  </section>

  <!-- Alerts & Recommendations -->
  <div class="alerts-panel" id="attention">
    <div class="alerts-panel-header">
      <div class="alerts-panel-title">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        Needs Attention
      </div>
      <span class="alerts-badge" id="attention-badge">Checking&hellip;</span>
    </div>
    <div class="alerts-body" id="attention-body"><ul id="attention-list" style="display:none;list-style:none;padding:0;margin:0"></ul>
      <div class="alert-item">
        <span class="alert-dot" style="background:var(--text-muted)"></span>
        <span class="alert-text">Checking routers&hellip;</span>
      </div>
    </div>
  </div>

  <!-- Router Cards -->
  <section class="cards-section">
    <div class="cards-section-header">
      <div class="section-title">Router Devices</div>
      <div class="router-search">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input id="router-search" type="text" placeholder="Search routers&hellip;" autocomplete="off">
      </div>
    </div>
    <div class="cards-grid">
      {cards}
    </div>
  </section>

  <!-- Detail Table -->
  <section class="table-section">
    <div class="table-section-header">
      <div class="section-title">Raw Metrics &amp; Interface Detail</div>
    </div>
    <div class="table-wrap">
      <table class="detail-table">
        <thead><tr>
          <th>Router</th><th>Status</th><th>Temp</th><th>CPU</th>
          <th>Memory</th><th>Interfaces</th><th>Down</th><th>Error</th>
        </tr></thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
  </section>

  <!-- Legend -->
  <div class="legend-section">
    <button class="legend-toggle" id="legend-toggle">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      What do these numbers mean?
      <svg class="legend-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left:auto;transition:transform .2s">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>
    <div class="legend-body" id="legend-body">
      <ul>
        <li><strong>CPU</strong> — under 50% is light, 50–79% moderate, 80%+ high (move heavy rules to another router).</li>
        <li><strong>Memory free</strong> — below 15% of total is low; below 10% is critical.</li>
        <li><strong>Temperature</strong> — under 55°C is cool, 55–69°C warm but normal, 70°C+ needs ventilation check. Some models have no sensor.</li>
        <li><strong>Interfaces up</strong> — running vs total. Disabled interfaces are not counted as down.</li>
        <li><strong>Trend lines</strong> — indigo is CPU, dashed violet is free memory over the last 24 hours.</li>
      </ul>
    </div>
  </div>

</div><!-- end .main-wrap -->

<script>
{_DASHBOARD_JS}
</script>
</body>
</html>
"""

def render_login_page(error: Optional[str] = None) -> str:
    """Simple password form shown when the dashboard requires a login."""
    message = (
        f'<div class="login-error">{_escape(error)}</div>'
        if error else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROS Manager — Login</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="login-wrap">
  <div class="login-card">
    <div class="login-icon">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <rect x="2" y="6" width="20" height="8" rx="2"/>
        <path d="M6 10h.01M10 10h.01"/>
        <path d="M12 18v-4"/><path d="M8 18h8"/>
      </svg>
    </div>
    <div class="login-title">ROS Manager</div>
    <div class="login-sub">Enter the team dashboard password to continue.</div>
    {message}
    <form method="post" action="/login">
      <label class="login-label" for="password">Password</label>
      <input class="login-input" id="password" name="password" type="password"
             autocomplete="current-password" required autofocus>
      <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center">Log in</button>
    </form>
  </div>
</div>
</body>
</html>
"""


def render_error_page(message: str) -> str:
    """Safe HTML page shown when the inventory cannot be loaded."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROS Manager — Error</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="error-wrap">
  <div class="error-card">
    <h1>ROS Manager</h1>
    <div class="error-msg">{_escape(message)}</div>
  </div>
</div>
</body>
</html>
"""
