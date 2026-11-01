<div align="center">

# ros-manager (`rosm`)

**Fleet management for MikroTik RouterOS devices, from the command line.**

Health checks · Configuration backups · Diffs · Safe restore · Scheduling · Web dashboard & HTTP API

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/RouterOS-API--SSL-informational)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Inventory Reference](#inventory-reference)
  - [Full Example](#full-example)
  - [Multi-file Inventories](#multi-file-inventories)
  - [Selecting Routers](#selecting-routers)
- [Command Reference](#command-reference)
  - [Exit Codes](#exit-codes)
  - [Restore and Verify](#restore-and-verify)
  - [Notifications](#notifications)
- [Output Formats](#output-formats)
- [Web Dashboard and HTTP API](#web-dashboard-and-http-api)
- [Security](#security)
- [Development](#development)
- [License](#license)

## Overview

`rosm` is a command-line manager for a fleet of MikroTik RouterOS devices. It
monitors device health, takes timestamped configuration backups, compares them,
and exposes everything through a scheduler, a web dashboard, and a JSON API.

Credentials are never stored in configuration files: passwords, bot tokens, and
webhook URLs are read exclusively from environment variables.

## Features

| Area | Capabilities |
| --- | --- |
| **Health checks** | CPU load, memory, temperature (when the model exposes a sensor), and interface status over the RouterOS API. |
| **Doctor diagnostics** | RouterOS version, uptime, board, architecture, CPU count, disk usage, voltage/fan sensors, and API round-trip latency. |
| **Backups** | Configuration export over SSH (`/export terse`), written atomically with UTC timestamps, with optional retention pruning. |
| **Diff & history** | Unified diffs between `.rsc` files; list stored backups and diff the two newest. |
| **Verify & restore** | Validate local backups (readable, non-empty, RouterOS sections, freshness). Restore defaults to a dry run; `--apply` uploads via SFTP and runs `/import` without rebooting. |
| **Notifications** | Telegram and/or webhook (generic, Slack, Discord) with flap detection, so alerts fire only when a router changes status. |
| **Scheduling** | Runs immediately, then repeats on a fixed interval. |
| **Reporting** | Self-contained HTML reports, plus text, JSON, and CSV output. |
| **Dashboard & API** | Colour-coded router cards with plain-language metric notes, an action recommendations panel, 24-hour CPU/memory trends (SQLite), backup buttons, an optional team password, and a JSON HTTP API. |
| **Inventories** | Selection by router or group; multi-file inventories via `include:` with globs and cycle detection. |

## Requirements

- Python **3.11+**
- RouterOS **API-SSL** enabled on each router (port `8729` by default)
- **SSH** access to each router for configuration exports
- Known host keys in `~/.ssh/known_hosts` (unknown hosts are rejected)

## Installation

```bash
python -m pip install -e '.[dev]'
```

This installs the `rosm` command. Verify the installation:

```bash
rosm --help
```

## Quick Start

**1. Create your inventory** from the example:

```bash
cp examples/inventory.example.yaml inventory.yaml
```

**2. Export each router's password** (never put it in the YAML):

```bash
export R1_PASS='your-router-password'
```

**3. Run a health check:**

```bash
rosm check --config inventory.yaml
```

**4. Inspect a router in detail:**

```bash
rosm doctor --config inventory.yaml --router core-1
```

**5. Back up every router:**

```bash
rosm backup --config inventory.yaml
```

**6. Compare two backups:**

```bash
rosm diff backups/core-1_20260101T000000.000000Z.rsc \
          backups/core-1_20260102T000000.000000Z.rsc
```

## Inventory Reference

The inventory is a YAML file describing your routers and global settings.
Validation fails fast with a message that points at the offending router and
field, and `rosm` never connects to a router if the inventory is invalid.
Duplicate router names are rejected, including duplicates across included files.

### Full Example

```yaml
backup_dir: backups          # optional, defaults to "backups"

# optional: keep only the newest N backups per router (default: keep all)
retention:
  keep_last: 14

# optional: load more routers from other files (string or list)
# paths are relative to this file; globs are expanded and includes recurse
include:
  - routers/core.yaml
  - routers/edge/*.yaml

routers:
  - name: core-1             # unique, required
    host: 192.168.88.1       # required
    username: admin          # required
    password_env: R1_PASS    # required: name of the env var holding the password
    groups: [core, backbone] # optional groups for --group filters
    api_port: 8729           # optional, default 8729 (8728 when api_tls: false)
    api_tls: true            # optional, default true
    api_ca_file: /path/ca.pem  # optional private CA for API-SSL
    ssh_port: 22             # optional, default 22
    ssh_known_hosts: ~/.ssh/known_hosts  # optional, default shown
    retention:               # optional per-router retention override
      keep_last: 30

# optional
notifications:
  telegram:
    token_env: TELEGRAM_BOT_TOKEN
    chat_id: "123456789"
  webhook:
    url_env: HOOK_URL
    style: generic          # generic | slack | discord

state_file: .rosm_state.json  # flap-detection state, default shown
metrics_db: metrics.db        # dashboard trend history (SQLite), default shown
```

> **Note:** The legacy top-level `telegram:` block is still accepted. A
> `notifications.telegram` block takes precedence when both are present.

### Multi-file Inventories

`routers` may live in the root file, in files listed under `include:`, or both.
Includes accept a single path or a list, expand globs, resolve relative paths
against the including file, and may themselves include more files. Missing
files and include cycles are reported as configuration errors.

```yaml
# inventory.yaml
backup_dir: backups
include:
  - routers/core/*.yaml
  - routers/edge.yaml
```

```yaml
# routers/edge.yaml
routers:
  - name: edge-1
    host: 192.168.89.1
    username: admin
    password_env: EDGE1_PASS
```

### Selecting Routers

`check`, `doctor`, `backup`, `run`, and `schedule` accept:

| Option | Description |
| --- | --- |
| `--router r1,r2` | Select routers by name. |
| `--group core,edge` | Select routers by group. Routers without `groups` belong to the implicit `default` group. |

When both options are given, a router is selected if it matches **any**
selector. Unknown names or groups exit with code `2` instead of silently
selecting nothing.

## Command Reference

| Command | Description |
| --- | --- |
| `rosm check --config PATH [--format text\|json\|csv\|html] [--output PATH]` | Health check every router. |
| `rosm doctor --config PATH [--format ...] [--output PATH]` | Version, board, disk, sensors, and API latency. |
| `rosm backup --config PATH` | Export and store the configuration of every router. |
| `rosm run --config PATH [--format text\|json\|csv\|html] [--output PATH] [--notify] [--notify-all]` | Check and back up, then summarize both. |
| `rosm diff OLD NEW` | Unified diff between two `.rsc` files. |
| `rosm verify FILE [--max-age-days N]` | Validate a local backup file. |
| `rosm restore --config PATH --router NAME --file PATH [--apply]` | Dry run (default) or upload and `/import`. |
| `rosm history --config PATH --router NAME [--diff]` | List backups or diff the two newest. |
| `rosm schedule --config PATH --interval-seconds N` | Run immediately, then repeat until stopped. |
| `rosm serve --config PATH [--host H] [--port P]` | Start the API server and dashboard. |

### Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | All routers succeeded. |
| `1` | At least one router check or backup failed (or `diff` found differences). |
| `2` | Invalid configuration, invalid options, or unreadable input. |

### Restore and Verify

`restore` is a **dry run** unless `--apply` is passed. The dry run prints the
target router, file size, a short preview, and a diff against the latest stored
backup, all without connecting to the device. With `--apply`, the file is
uploaded via SFTP and imported; the router is never rebooted automatically.

`verify` exits `0` when the file is valid, `1` when its contents look wrong,
and `2` when it cannot be read.

### Notifications

`run --notify` sends alerts only when a router changes status, compared against
`state_file`. Use `--notify-all` to force a full summary. `rosm schedule` uses
the same flap-aware notifications on every cycle.

## Output Formats

| Format | Description |
| --- | --- |
| `text` | One line per router with status and metric summary, followed by an error section when anything failed. |
| `json` | `{"generated_at": "...", "routers": [...]}` with per-router health, interfaces, and (for `run`) backup results. |
| `csv` | One row per router with a fixed header. Missing sensor values are written as empty fields. |
| `html` | Self-contained report (inline CSS, no external assets) for `check` and `run`. Ideal with `--output report.html` for sharing or archiving. |

## Web Dashboard and HTTP API

```bash
rosm serve --config inventory.yaml --host 127.0.0.1 --port 8000
```

The dashboard UI uses a self-hosted Tailwind browser build (`src/ros_manager/static/tailwind.min.js`, served at `/static/tailwind.min.js`) so it works offline and needs no CDN.

The dashboard is built for the whole team: junior support staff get
colour-coded cards and plain-language notes, while seniors can open the raw
metrics table for every router.

| Element | Description |
| --- | --- |
| Status cards | One card per router, coloured green (healthy), amber (warning), or red (error). Each card explains CPU, memory, temperature, and interface state in plain language. |
| Needs attention | A recommendations panel that turns warnings into next steps, e.g. "move heavy firewall rules to another router" or "check the cable or the peer device". |
| Trends | CPU (blue) and free memory (dashed purple) sparklines for the last 24 hours, stored in `metrics_db`. |
| Advanced | A collapsible raw-metrics table with the full interface and error detail. |

**Optional team password.** By default the dashboard is open, which is fine
for `127.0.0.1` or an internal VLAN. To require a login, export a shared
password before starting the server:

```bash
export ROSM_DASH_PASSWORD='your-team-password'
rosm serve --config inventory.yaml
```

`rosm serve` prints a hint when the password is unset. The password is read
only from the environment, sessions last 12 hours, and `POST /logout` ends
one. This is deliberately a single shared password; role-based access is not
part of the dashboard yet.

| Endpoint | Description |
| --- | --- |
| `GET /` | Dashboard with status cards, recommendations, trends, and backup buttons. |
| `GET /login`, `POST /login`, `POST /logout` | Password login when `ROSM_DASH_PASSWORD` is set. |
| `GET /api/status` | Run health checks and return `{"generated_at", "routers": [...]}`. Results are cached for 10 seconds so several dashboard tabs do not duplicate checks. |
| `GET /api/history?hours=24` | Return stored trend points per router (`hours` is clamped to 1–720). |
| `POST /api/backups` | Back up every router and return the combined result. |
| `POST /api/backups/{name}` | Back up one router (`404` for an unknown name). |
| `POST /backups` | Legacy alias for `POST /api/backups`. |

**Behavior notes**

- Responses are always HTTP `200` with per-router status when a router fails,
  so one broken device never hides the rest.
- A startup configuration error makes every endpoint return `500` with a safe
  message. If the inventory cannot be loaded at all, `rosm serve` exits early
  with code `2`.
- The dashboard polls `/api/status` every 30 seconds and is read-only apart
  from the backup buttons, which ask for confirmation first.
- Trend history is best-effort: it is written on every status check, pruned to
  30 days when the server starts, and a locked or corrupt database never
  breaks a health check.

## Security

- **Secrets stay out of files.** Passwords, bot tokens, and webhook URLs are
  read from environment variables only and never appear in YAML, logs, or API
  responses.
- **TLS by default.** API-SSL certificates are validated; plain API is used
  only when `api_tls: false` is set explicitly.
- **Strict SSH host keys.** Keys are verified against `ssh_known_hosts`;
  unknown or mismatched hosts are rejected.
- **Safe restore.** `restore` is a dry run unless `--apply` is passed, and it
  never reboots the router.
- **Minimal state.** The notification state file stores only router names and
  statuses; the trend database stores only timestamps and numeric metrics.
- **Optional dashboard login.** Set `ROSM_DASH_PASSWORD` to require a shared
  team password; the password is never written to disk or returned by the API.
- **Sanitized errors.** The dashboard and API never return credentials, and
  error messages are sanitized before reaching the client.
- **Sensitive exports excluded.** RouterOS `/export` omits sensitive values
  unless `show-sensitive` is used, and `rosm` never requests it. A `.rsc` file
  is a configuration export, not a full binary clone of the device.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

The test suite uses mocks only: no real routers, network access, or Telegram
tokens are required.

### Package Layout

```
src/ros_manager/
├── config.py      # inventory loading and validation
├── models.py      # dataclasses shared across the app
├── router.py      # RouterOS API + SSH adapter (health, doctor, export)
├── service.py     # per-router orchestration, selection, retention
├── storage.py     # atomic, timestamped backups + pruning + history
├── restore.py     # verify local backups + SSH restore
├── notify.py      # multi-channel notifications + flap state
├── metrics.py     # SQLite trend history for the dashboard
├── auth.py        # optional single-password dashboard login
├── scheduler.py   # interval scheduler
├── telegram.py    # Telegram transport
├── serialize.py   # shared JSON-serializable result builders
├── report.py      # HTML report + dashboard renderers
├── api.py         # FastAPI app (dashboard + JSON API)
└── cli/           # one module per command, shared helpers in common.py
```

## License

Released under the MIT License. See [LICENSE](LICENSE) for details.
