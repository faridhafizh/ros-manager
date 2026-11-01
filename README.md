# ros-manager

`rosm` — a command-line manager for a fleet of MikroTik RouterOS devices.
Health checks, configuration backups, diffs, scheduling, and an HTTP API —
with secrets read only from environment variables.

> **Status:** All four phases are complete: rename/modularization, doctor +
> retention + selection, verify/restore/history + notifications, and HTML
> reports, the web dashboard, and multi-file inventories.

## Features

- **Health checks** over the RouterOS API: CPU load, memory, temperature
  (when the model exposes a sensor), and interface status.
- **Doctor diagnostics**: RouterOS version, uptime, board, architecture, CPU
  count, disk usage, voltage/fan sensors, and API round-trip latency.
- **Router selection** with `--router` and `--group` on every fleet command.
- **Configuration backups** over SSH (`/export terse`), written atomically
  with UTC timestamps, plus optional **retention/pruning** of old backups.
- **Unified diffs** between two `.rsc` backup files.
- **Verify** local backups (readable, non-empty, RouterOS sections, freshness).
- **Restore** with a safe dry-run by default; `--apply` uploads via SFTP and
  runs `/import` without rebooting.
- **History** of stored backups, including a diff of the two newest.
- **Multi-channel notifications** (Telegram and/or webhook) with flap
  detection: alerts are sent only when a router changes status.
- **Scheduling** that runs immediately, then repeats on an interval.
- **Self-contained HTML reports** for `check` and `run` (`--format html`).
- **Web dashboard** with live status and per-router backup buttons.
- **HTTP API** (`/api/status`, `/api/backups`, `/api/backups/{name}`).
- **Multi-file inventories** via `include:` with globs and cycle detection.
- **Structured output**: terminal text, JSON, CSV, or HTML.

## Requirements

- Python 3.11+
- RouterOS API-SSL enabled on each router (port 8729 by default)
- SSH access to each router for configuration exports
- Known host keys in `~/.ssh/known_hosts` (unknown hosts are rejected)

## Install

```bash
python -m pip install -e '.[dev]'
```

This installs the `rosm` command.

```bash
rosm --help
```

## Quick start

1. Copy the example inventory and edit it:

   ```bash
   cp examples/inventory.example.yaml inventory.yaml
   ```

2. Export the password for each router (never put it in the YAML):

   ```bash
   export R1_PASS='your-router-password'
   ```

3. Run a health check:

   ```bash
   rosm check --config inventory.yaml
   ```

4. Inspect a router in detail:

   ```bash
   rosm doctor --config inventory.yaml --router core-1
   ```

5. Back up every router:

   ```bash
   rosm backup --config inventory.yaml
   ```

6. Compare two backups:

   ```bash
   rosm diff backups/core-1_20260101T000000.000000Z.rsc \
             backups/core-1_20260102T000000.000000Z.rsc
   ```

## Inventory format

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
```

The legacy top-level `telegram:` block is still accepted; a
`notifications.telegram` block takes precedence when both are present.

Validation fails fast with a message that points at the offending router and
field. The process never connects to a router if the inventory is invalid.
Duplicate router names are rejected, including duplicates across included
files.

### Multi-file inventories

`routers` may live in the root file, in files listed under `include:`, or in
both. Includes accept a single path or a list, expand globs, resolve relative
paths against the including file, and may themselves include more files.
Missing files and include cycles are reported as config errors.

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

### Selecting routers

`check`, `backup`, `run`, `doctor`, and `schedule` accept:

- `--router r1,r2` — select by name.
- `--group core,edge` — select by group; routers without `groups` belong to
  the implicit `default` group.

When both are given, a router is selected if it matches **any** selector.
Unknown names or groups exit with code 2 instead of silently selecting
nothing.

## Commands

| Command | Description |
| --- | --- |
| `rosm check --config PATH [--format text\|json\|csv\|html] [--output PATH]` | Health check every router. |
| `rosm doctor --config PATH [--format ...] [--output PATH]` | Version, board, disk, sensors, and API latency. |
| `rosm backup --config PATH` | Export and store the configuration of every router. |
| `rosm run --config PATH [--format text\|json\|csv\|html] [--output PATH] [--notify] [--notify-all]` | Check + back up, then summarize both. |
| `rosm diff OLD NEW` | Unified diff between two `.rsc` files. |
| `rosm verify FILE [--max-age-days N]` | Validate a local backup file. |
| `rosm restore --config PATH --router NAME --file PATH [--apply]` | Dry-run (default) or upload + `/import`. |
| `rosm history --config PATH --router NAME [--diff]` | List backups or diff the two newest. |
| `rosm schedule --config PATH --interval-seconds N` | Run immediately, then repeat until stopped. |
| `rosm serve --config PATH [--host H] [--port P]` | Start the API server and dashboard. |

`check`, `doctor`, `backup`, `run`, and `schedule` also accept
`--router NAME[,NAME...]` and `--group NAME[,NAME...]`.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All routers succeeded. |
| `1` | At least one router check or backup failed (or `diff` found differences). |
| `2` | Invalid configuration, invalid options, or unreadable input. |

`restore` is a dry-run unless `--apply` is passed: it prints the target
router, file size, a short preview, and a diff against the latest stored
backup without connecting. `verify` exits `0` when the file is valid, `1`
when its contents look wrong, and `2` when it cannot be read.

`run --notify` sends alerts only when a router changes status (compared with
`state_file`). Use `--notify-all` to force a full summary. `rosm schedule`
uses the same flap-aware notifications on every cycle.

## Output formats

- **text** — one line per router with status and metric summary, followed by an
  error section when anything failed.
- **json** — `{"generated_at": "...", "routers": [...]}` with per-router health,
  interfaces, and (for `run`) backup results.
- **csv** — one row per router with a fixed header. Missing sensor values are
  written as empty fields.
- **html** — a self-contained report (inline CSS, no external assets) for
  `check` and `run`. Useful with `--output report.html` for sharing or archiving.

## Web dashboard and API

```bash
rosm serve --config inventory.yaml --host 127.0.0.1 --port 8000
```

| Endpoint | Description |
| --- | --- |
| `GET /` | Dashboard with live per-router status and backup buttons. |
| `GET /api/status` | Run health checks and return `{"generated_at", "routers": [...]}`. |
| `POST /api/backups` | Back up every router and return the combined result. |
| `POST /api/backups/{name}` | Back up one router (`404` for an unknown name). |
| `POST /backups` | Legacy alias for `POST /api/backups`. |

Responses are always HTTP `200` with per-router status when a router fails, so
one broken device never hides the rest. A startup config error makes every
endpoint return `500` with a safe message; if the inventory cannot be loaded at
all, `rosm serve` exits early with code `2`. The dashboard polls
`/api/status` every 30 seconds and is read-only apart from the backup buttons.

## Security notes

- Passwords, bot tokens, and webhook URLs are read from environment variables
  only; they never appear in YAML, logs, or API responses.
- API-SSL certificates are validated by default. Plain API is used only when
  `api_tls: false` is set explicitly.
- SSH host keys are verified against `ssh_known_hosts`; unknown or mismatched
  hosts are rejected.
- `restore` is a dry-run unless `--apply` is passed, and it never reboots the
  router automatically.
- The notification state file (default `.rosm_state.json`) stores only router
  names and statuses, never secrets.
- The dashboard and API never return passwords, tokens, or webhook URLs; error
  messages are sanitized before they reach the client.
- RouterOS `/export` omits sensitive values unless `show-sensitive` is used;
  ROS Manager never requests it. A `.rsc` file is a configuration export, not
  a full binary clone of the device.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
```

The test suite uses mocks only: no real routers, network access, or Telegram
tokens are required.

### Package layout

```
src/ros_manager/
├── config.py      # inventory loading and validation
├── models.py      # dataclasses shared across the app
├── router.py      # RouterOS API + SSH adapter (health, doctor, export)
├── service.py     # per-router orchestration, selection, retention
├── storage.py     # atomic, timestamped backups + pruning + history
├── restore.py     # verify local backups + SSH restore
├── notify.py      # multi-channel notifications + flap state
├── scheduler.py   # interval scheduler
├── telegram.py    # Telegram transport
├── serialize.py   # shared JSON-serializable result builders
├── report.py      # HTML report + dashboard renderers
├── api.py         # FastAPI app (dashboard + JSON API)
└── cli/           # one module per command, shared helpers in common.py
```

## License

MIT — see [LICENSE](LICENSE).
