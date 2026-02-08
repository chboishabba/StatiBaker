# Daemon + Web Control Plane (Win/Mac/Linux)

This document defines a single local daemon model for StatiBaker collectors and
daily build wrappers, managed from the webpage instead of per-host ad hoc cron
or shell scripts.

## Goal

Provide one cross-platform runtime pattern where:
- collectors/connectors run under one supervisor daemon,
- scheduling and on-demand runs are controlled from the web UI,
- job state and history are persisted locally,
- all behavior remains metadata-only and append-only.

## Non-goals

- No cloud control plane requirement.
- No remote command-and-control by default.
- No automatic content promotion beyond existing SB boundaries.

## Runtime Model

Use a local process called `sb-supervisor` with three responsibilities:

1. `collector orchestration`
- start/stop/restart connectors (NotebookLM, media, social, system adapters),
- enforce per-connector config and retention policy,
- write normalized outputs into day-scoped SB paths.

2. `scheduler`
- interval jobs (e.g., every 10m NotebookLM metadata snapshot),
- daily bake jobs (`capture -> normalize -> run_day`),
- retry/backoff and failure state transitions.

3. `web control API`
- localhost-only control and status API,
- consumed by the existing dashboard/web UI,
- exposes run queue, connector health, and recent logs/artifacts.

## Web UI Management Requirements

The webpage should manage daemon behavior directly:

- Connector toggles:
  - enabled/disabled
  - run mode (manual / interval / daily)
  - schedule configuration
- Job controls:
  - run now
  - pause queue
  - cancel pending job
  - retry failed job
- Visibility:
  - connector health
  - last success / last error
  - active run progress
  - output artifact links
- Drill-down:
  - per-job logs
  - adapter warnings
  - normalized output counts

## Cross-Platform Service Installation

The daemon binary/process is the same; service registration differs by OS:

- Linux:
  - systemd user service (`~/.config/systemd/user/sb-supervisor.service`)
  - optional companion timer for heartbeat/bootstrap only
- macOS:
  - launchd agent (`~/Library/LaunchAgents/com.stati.baker.supervisor.plist`)
- Windows:
  - per-user background service wrapper (or scheduled task fallback)
  - standard log path under local app data

Installers should expose one unified command surface:
- `sb-supervisor install`
- `sb-supervisor uninstall`
- `sb-supervisor start|stop|status`

## Local Persistence

Persist daemon state in local SQLite (example):
- `runs/control/sb_supervisor.sqlite`

Suggested tables:
- `connectors`
  - id, type, enabled, schedule_json, config_json, updated_at
- `jobs`
  - job_id, connector_id, job_type, status, queued_at, started_at, finished_at
- `job_attempts`
  - job_id, attempt_no, status, error_code, error_text, duration_ms
- `artifacts`
  - job_id, kind, path, bytes, created_at
- `daemon_events`
  - ts, level, event_type, payload_json

## API Contract (Localhost)

Suggested endpoints:
- `GET /api/daemon/status`
- `GET /api/daemon/connectors`
- `PATCH /api/daemon/connectors/{id}`
- `POST /api/daemon/jobs/run`
- `GET /api/daemon/jobs?status=...`
- `GET /api/daemon/jobs/{id}`
- `POST /api/daemon/jobs/{id}/retry`
- `POST /api/daemon/jobs/{id}/cancel`

Rules:
- bind localhost only by default,
- reject unauthenticated mutation endpoints,
- include explicit provenance fields in API responses.

## NotebookLM + Snapshot Archival in Daemon

NotebookLM connector should be daemon-managed, not manually scripted:
- capture metadata snapshots on schedule,
- normalize to `notes_meta`,
- optionally archive raw snapshots in local SQLite with dedupe key:
  - `(app, event_type, notebook_id_hash, note_id_hash, ts_bucket)`
- expose trend queries in UI:
  - notebooks touched/day
  - source churn
  - create/modify/move/delete counts over time

## Security and Boundary Rules

- Localhost-only API unless explicitly opted into remote mode.
- Metadata-only enforcement at adapter boundary.
- No plaintext secret rendering in UI or logs.
- All mutating actions produce an auditable `daemon_events` row.
- Fail closed for invalid connector configs.

## Rollout Phases

1. `Phase 1`: daemon skeleton + local API + status page wiring.
2. `Phase 2`: NotebookLM and daily bake wrappers under daemon control.
3. `Phase 3`: media/social/system connectors migrated to daemon jobs.
4. `Phase 4`: web-first management (remove dependency on manual cron/systemd wrappers in docs).

## Open Decisions

- Final auth model for localhost mutation endpoints.
- Windows service wrapper choice.
- Whether to store job logs inline in SQLite vs file + index.
- Retention defaults for `jobs`/`artifacts` history.
